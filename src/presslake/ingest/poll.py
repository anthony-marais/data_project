"""
Poll des flux RSS : fetch HTTP, parse XML, déduplication, bronze, catalogue.

Chaîne complète (modules 02–04) :
  Feed.url → httpx GET → feedparser → entries[]
  → clé composite → seen.json
  → si nouveau : write_entry_bronze() → MinIO
              → upsert_fetched_article() → Postgres
"""

from pathlib import Path

import feedparser
import httpx
import psycopg
from botocore.client import BaseClient

from presslake.catalog.articles import upsert_fetched_article
from presslake.ingest.bronze import item_key, write_entry_bronze
from presslake.ingest.feeds import Feed
from presslake.ingest.seen import DEFAULT_SEEN_PATH, load_seen, mark_seen, save_seen
from presslake.observability.metrics import record_poll_finished
from presslake.observability.worker_runs import JOB_POLL, log_worker_run
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_bucket, get_s3_client

USER_AGENT = "PressLake/0.1 (learning; local dev)"


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Télécharge et parse un flux RSS/Atom."""
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return feedparser.parse(response.text)


def composite_key(feed: Feed, entry: dict) -> str:
    """Clé dédup locale (seen.json) : feed_id + item_key."""
    return f"{feed.id}:{item_key(entry)}"


def poll_feed(
    feed: Feed,
    seen: dict[str, str],
    *,
    s3_client: BaseClient,
    bucket: str,
    conn: psycopg.Connection,
) -> int:
    """
    Poll un flux : dédup + bronze + catalogue pour les nouveaux items.

    Args:
        conn: connexion Postgres (une par run, commit par article nouveau).
    """
    parsed = fetch_feed(feed.url)
    new_count = 0

    for entry in parsed.entries:
        key = composite_key(feed, entry)

        if mark_seen(seen, key):
            continue

        new_count += 1
        title = entry.get("title", "(sans titre)")

        # Module 03 : objet immuable dans MinIO.
        s3_uri = write_entry_bronze(s3_client, bucket, feed, entry)

        # Module 04 : ligne catalogue (url unique, idempotent).
        upsert_fetched_article(conn, feed, entry, s3_uri=s3_uri)
        conn.commit()

        print(f"[NEW] {feed.id} | {title} | {s3_uri}")

    return new_count


def poll_all_dedup(
    feeds: list[Feed],
    seen_path: Path = DEFAULT_SEEN_PATH,
) -> int:
    """
    Poll tous les flux : seen.json + bronze + Postgres.

    Critère *done* module 04 :
      - 1er run : lignes dans articles + objets bronze
      - 2e run  : → 0 nouvel(s) item(s), count articles inchangé
    """
    s3_client = get_s3_client()
    bucket = get_bucket()

    seen = load_seen(seen_path)
    total_new = 0

    with get_connection() as conn:
        for feed in feeds:
            total_new += poll_feed(
                feed,
                seen,
                s3_client=s3_client,
                bucket=bucket,
                conn=conn,
            )
        log_worker_run(conn, JOB_POLL, new_items=total_new)
        conn.commit()

    save_seen(seen, seen_path)
    record_poll_finished(new_articles=total_new)
    print(f"\n→ {total_new} nouvel(s) item(s)")

    return total_new
