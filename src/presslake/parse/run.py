"""
Boucle de parsing : articles fetched → silver + status parsed.
"""

import psycopg
from botocore.client import BaseClient

from presslake.catalog.articles import list_articles_by_status, mark_parsed
from presslake.parse.extract import extract_text_from_bronze
from presslake.parse.silver import write_silver_from_bronze
from presslake.observability.metrics import record_parse_finished
from presslake.observability.worker_runs import JOB_PARSE, log_worker_run
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_bucket, get_json_object, get_s3_client, parse_s3_uri

STATUS_FETCHED = "fetched"


def parse_article(
    conn: psycopg.Connection,
    s3_client: BaseClient,
    bucket: str,
    article: dict,
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

    # Le bucket catalogue peut différer en théorie ; on lit l'URI enregistrée.
    bronze = get_json_object(s3_client, bronze_bucket, bronze_key)

    text, text_source = extract_text_from_bronze(bronze)

    silver_uri = write_silver_from_bronze(
        s3_client,
        bucket,
        bronze,
        bronze_s3_uri=bronze_uri,
        bronze_key=bronze_key,
        text=text,
        text_source=text_source,
    )

    mark_parsed(conn, article["url"], silver_uri)
    conn.commit()

    title = article.get("title") or bronze.get("title") or "(sans titre)"
    print(f"[PARSED] {article['feed_id']} | {title[:60]} | {silver_uri} ({text_source})")

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

        for article in articles:
            try:
                parse_article(conn, s3_client, bucket, article)
                parsed_count += 1
            except (ValueError, OSError) as exc:
                errors += 1
                print(f"[SKIP] {article.get('url', '?')} — {exc}")

        log_worker_run(conn, JOB_PARSE, new_items=parsed_count, errors=errors)
        conn.commit()

    print(f"\n→ {parsed_count} article(s) parsé(s)", end="")
    if errors:
        print(f", {errors} ignoré(s)")
    else:
        print()

    record_parse_finished(parsed=parsed_count, errors=errors)
    return parsed_count
