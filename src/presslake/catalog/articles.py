"""
Upsert articles dans le catalogue Postgres.

Une ligne par article : url unique, pointeur s3_uri, hash, statut pipeline.
"""

from datetime import datetime, timezone
from typing import Any

import psycopg

from presslake.ingest.bronze import content_hash, item_key
from presslake.ingest.feeds import Feed

# Statuts pipeline (voir schema.sql CHECK constraint).
STATUS_FETCHED = "fetched"


def _parse_published_at(entry: dict) -> datetime | None:
    """
    Convertit published_parsed (struct time feedparser) en datetime UTC.

    Retourne None si la date est absente (colonne nullable).
    """
    published = entry.get("published_parsed")
    if not published:
        return None
    return datetime(*published[:6], tzinfo=timezone.utc)


def upsert_fetched_article(
    conn: psycopg.Connection,
    feed: Feed,
    entry: dict,
    *,
    s3_uri: str,
) -> bool:
    """
    Enregistre un article fraîchement écrit en bronze.

    Idempotence : ON CONFLICT (url) DO NOTHING — 2ᵉ ingest = 0 nouvelle ligne.

    Args:
        conn: connexion Postgres ouverte.
        feed: flux source.
        entry: entry feedparser.
        s3_uri: URI retournée par write_entry_bronze().

    Returns:
        True si une nouvelle ligne a été insérée, False si déjà présente (url).

    Raises:
        ValueError: si l'entry n'a pas de link (url catalogue impossible).
    """
    url = entry.get("link")
    if not url:
        raise ValueError(
            f"article sans url (link) — impossible catalogue : "
            f"feed={feed.id!r} title={entry.get('title')!r}"
        )

    stable_key = item_key(entry)
    row_hash = content_hash(stable_key)

    result = conn.execute(
        """
        INSERT INTO articles (
            feed_id, url, item_key, content_hash, s3_uri,
            title, published_at, status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (url) DO NOTHING
        """,
        (
            feed.id,
            str(url).strip(),
            stable_key,
            row_hash,
            s3_uri,
            entry.get("title"),
            _parse_published_at(entry),
            STATUS_FETCHED,
        ),
    )

    # rowcount = 1 si INSERT, 0 si conflit (DO NOTHING).
    return result.rowcount == 1


def count_articles(conn: psycopg.Connection) -> int:
    """Nombre total d'articles catalogue — utile pour vérif module 04."""
    row = conn.execute("SELECT count(*) FROM articles").fetchone()
    return int(row[0]) if row else 0


def list_recent(
    conn: psycopg.Connection,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Derniers articles ingérés (debug / notebook)."""
    rows = conn.execute(
        """
        SELECT feed_id, title, url, s3_uri, status, fetched_at
        FROM articles
        ORDER BY fetched_at DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()

    return [
        {
            "feed_id": r[0],
            "title": r[1],
            "url": r[2],
            "s3_uri": r[3],
            "status": r[4],
            "fetched_at": r[5],
        }
        for r in rows
    ]
