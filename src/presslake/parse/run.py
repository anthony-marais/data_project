"""
Boucle de parsing : articles fetched → silver + status parsed.
"""

import psycopg
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from presslake.catalog.articles import list_articles_by_status, mark_parsed
from presslake.events.consumer import article_dict_from_event, iter_article_ingested
from presslake.ingest.feeds import feed_lang_by_id
from presslake.observability.metrics import record_parse_finished
from presslake.observability.worker_runs import JOB_PARSE, log_worker_run
from presslake.output import info, report_progress
from presslake.parse.extract import extract_text_from_bronze
from presslake.parse.lang import detect_content_lang
from presslake.parse.silver import write_silver_from_bronze
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_bucket, get_json_object, get_s3_client, parse_s3_uri

STATUS_FETCHED = "fetched"


def resolve_feed_lang(article: dict) -> str:
    """Langue déclarée du flux (catalogue ou feeds.yml)."""
    if article.get("feed_lang"):
        return article["feed_lang"]
    return feed_lang_by_id().get(article["feed_id"], "und")


def parse_article(
    conn: psycopg.Connection,
    s3_client: BaseClient,
    bucket: str,
    article: dict,
    *,
    reparse: bool = False,
) -> str:
    """
    Parse un article catalogue : bronze → silver → update Postgres.

    Args:
        article: ligne avec url, s3_uri (bronze), feed_id, etc.

    Returns:
        silver_s3_uri écrit.

    Raises:
        ValueError: si extraction texte impossible.
    """
    bronze_uri = article["s3_uri"]
    bronze_bucket, bronze_key = parse_s3_uri(bronze_uri)

    bronze = get_json_object(s3_client, bronze_bucket, bronze_key)

    text, text_source = extract_text_from_bronze(bronze)
    feed_lang = resolve_feed_lang(article)
    title = article.get("title") or bronze.get("title") or ""
    detect_input = f"{title}\n{text}".strip()
    content_lang, confidence = detect_content_lang(detect_input, fallback=feed_lang)

    silver_uri = write_silver_from_bronze(
        s3_client,
        bucket,
        bronze,
        bronze_s3_uri=bronze_uri,
        bronze_key=bronze_key,
        text=text,
        text_source=text_source,
        feed_lang=feed_lang,
        content_lang=content_lang,
        content_lang_confidence=confidence,
    )

    mark_parsed(
        conn,
        article["url"],
        silver_uri,
        feed_lang=feed_lang,
        content_lang=content_lang,
        reparse=reparse,
    )
    conn.commit()

    display_title = title or "(sans titre)"
    info(
        f"[PARSED] {article['feed_id']} | {display_title[:60]} | "
        f"{silver_uri} ({text_source}, lang={content_lang})"
    )

    return silver_uri


def parse_all(*, limit: int | None = None) -> int:
    """
    Parse tous les articles en status=fetched.

    Args:
        limit: nombre max d'articles (debug). None = tous.

    Returns:
        Nombre d'articles parsés avec succès.
    """
    s3_client = get_s3_client()
    bucket = get_bucket()
    parsed_count = 0
    errors = 0

    with get_connection() as conn:
        articles = list_articles_by_status(conn, STATUS_FETCHED, limit=limit)

        article_total = len(articles)
        for index, article in enumerate(articles, start=1):
            try:
                parse_article(conn, s3_client, bucket, article)
                parsed_count += 1
            except (ValueError, OSError) as exc:
                errors += 1
                print(f"[SKIP] {article.get('url', '?')} — {exc}")
            report_progress(index, article_total)

        log_worker_run(conn, JOB_PARSE, new_items=parsed_count, errors=errors)
        conn.commit()

    info(f"\n→ {parsed_count} article(s) parsé(s)", end="")
    if errors:
        info(f", {errors} ignoré(s)")
    else:
        info()

    record_parse_finished(parsed=parsed_count, errors=errors)
    return parsed_count


def parse_from_kafka(*, replay: bool = False, limit: int | None = None) -> int:
    """
    Parse via le bus Kafka : consomme article.ingested → silver.

    Args:
        replay: rejeu depuis l'offset 0 (reconstruit le silver).
        limit: nombre max d'événements à traiter.
    """
    s3_client = get_s3_client()
    bucket = get_bucket()
    parsed_count = 0
    errors = 0

    with get_connection() as conn:
        for event in iter_article_ingested(replay=replay, limit=limit):
            article = article_dict_from_event(event)
            try:
                parse_article(
                    conn,
                    s3_client,
                    bucket,
                    article,
                    reparse=replay,
                )
                parsed_count += 1
            except (ValueError, OSError, KeyError, ClientError) as exc:
                errors += 1
                print(f"[SKIP] {article.get('url', '?')} — {exc}")
            report_progress(parsed_count + errors, None)

        log_worker_run(conn, JOB_PARSE, new_items=parsed_count, errors=errors)
        conn.commit()

    mode = "replay" if replay else "kafka"
    info(f"\n→ {parsed_count} article(s) parsé(s) ({mode})", end="")
    if errors:
        info(f", {errors} ignoré(s)")
    else:
        info()

    record_parse_finished(parsed=parsed_count, errors=errors)
    return parsed_count
