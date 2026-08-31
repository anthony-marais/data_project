"""
Poll des flux RSS : fetch HTTP, parse XML, déduplication, écriture bronze.

Chaîne complète (module 02 + 03) :
  Feed.url → httpx GET → feedparser → entries[]
  → clé composite (feed_id + item_key) → seen.json
  → si nouveau : write_entry_bronze() → MinIO
"""

from pathlib import Path

import feedparser
import httpx
from botocore.client import BaseClient

from presslake.ingest.bronze import item_key, write_entry_bronze
from presslake.ingest.feeds import Feed
from presslake.ingest.seen import DEFAULT_SEEN_PATH, load_seen, mark_seen, save_seen
from presslake.storage.s3 import get_bucket, get_s3_client

# Certains médias (France24, RFI, CNIL) renvoient 403 sans User-Agent explicite.
USER_AGENT = "PressLake/0.1 (learning; local dev)"


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """
    Télécharge un flux RSS/Atom et le parse.

    Args:
        url: URL du flux (ex. https://www.france24.com/fr/rss).

    Returns:
        Objet feedparser avec .feed (métadonnées) et .entries (liste d'articles).

    Raises:
        httpx.HTTPStatusError: si le serveur répond 4xx ou 5xx.
    """
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()

    return feedparser.parse(response.text)


def composite_key(feed: Feed, entry: dict) -> str:
    """
    Clé unique par flux ET par article (dédup locale seen.json).

    Ex. : "france24:uuid-abc"
    """
    return f"{feed.id}:{item_key(entry)}"


def poll_feed(
    feed: Feed,
    seen: dict[str, str],
    *,
    s3_client: BaseClient,
    bucket: str,
) -> int:
    """
    Poll un flux : dédup + écriture bronze pour les nouveaux items.

    Args:
        feed: flux à interroger.
        seen: clés déjà vues (modifié en place).
        s3_client: client boto3 (créé une fois par run).
        bucket: nom du bucket MinIO (ex. presslake).

    Returns:
        Nombre d'items nouveaux écrits en bronze pour ce flux.
    """
    parsed = fetch_feed(feed.url)
    new_count = 0

    for entry in parsed.entries:
        key = composite_key(feed, entry)

        if mark_seen(seen, key):
            continue

        new_count += 1
        title = entry.get("title", "(sans titre)")

        # Module 03 : persistance immuable dans le lake.
        s3_uri = write_entry_bronze(s3_client, bucket, feed, entry)
        print(f"[NEW] {feed.id} | {title} | {s3_uri}")

    return new_count


def poll_all_dedup(
    feeds: list[Feed],
    seen_path: Path = DEFAULT_SEEN_PATH,
) -> int:
    """
    Poll tous les flux : seen.json + bronze MinIO.

    Workflow :
      1. Client S3 + bucket (une fois)
      2. Charger seen.json
      3. Pour chaque feed → poll_feed (fetch, dédup, bronze)
      4. Sauvegarder seen.json

    Critère *done* :
      - 1er run : [NEW] + s3://presslake/bronze/…
      - 2e run  : → 0 nouvel(s) item(s)
    """
    s3_client = get_s3_client()
    bucket = get_bucket()

    seen = load_seen(seen_path)
    total_new = 0

    for feed in feeds:
        total_new += poll_feed(feed, seen, s3_client=s3_client, bucket=bucket)

    save_seen(seen, seen_path)
    print(f"\n→ {total_new} nouvel(s) item(s)")

    return total_new
