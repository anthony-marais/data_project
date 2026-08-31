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
STATUS_PARSED = "parsed"
STATUS_INDEXED = "indexed"
STATUS_EMBEDDED = "embedded"


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
            title, published_at, status, feed_lang
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
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
            feed.lang,
        ),
    )

    # rowcount = 1 si INSERT, 0 si conflit (DO NOTHING).
    return result.rowcount == 1


def list_articles_by_status(
    conn: psycopg.Connection,
    status: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Liste les articles catalogue par statut pipeline.

    Utilisé par `presslake parse` pour ne traiter que status=fetched.
    """
    sql = """
        SELECT feed_id, title, url, s3_uri, content_hash, status, silver_s3_uri,
               feed_lang, content_lang
        FROM articles
        WHERE status = %s
        ORDER BY fetched_at ASC
    """
    params: list[Any] = [status]

    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    return [
        {
            "feed_id": r[0],
            "title": r[1],
            "url": r[2],
            "s3_uri": r[3],
            "content_hash": r[4],
            "status": r[5],
            "silver_s3_uri": r[6],
            "feed_lang": r[7],
            "content_lang": r[8],
        }
        for r in rows
    ]


def list_articles_to_index(
    conn: psycopg.Connection,
    *,
    include_indexed: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Articles prêts pour OpenSearch (parsed, ou aussi indexed si re-index).
    """
    statuses = [STATUS_PARSED]
    if include_indexed:
        statuses.append(STATUS_INDEXED)

    sql = """
        SELECT feed_id, title, url, s3_uri, content_hash, status, silver_s3_uri,
               feed_lang, content_lang
        FROM articles
        WHERE status = ANY(%s)
        ORDER BY fetched_at ASC
    """
    params: list[Any] = [statuses]

    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    return [
        {
            "feed_id": r[0],
            "title": r[1],
            "url": r[2],
            "s3_uri": r[3],
            "content_hash": r[4],
            "status": r[5],
            "silver_s3_uri": r[6],
            "feed_lang": r[7],
            "content_lang": r[8],
        }
        for r in rows
    ]


def mark_parsed(
    conn: psycopg.Connection,
    url: str,
    silver_s3_uri: str,
    *,
    feed_lang: str,
    content_lang: str,
    reparse: bool = False,
) -> None:
    """
    Passe un article en status=parsed et enregistre le pointeur silver.

    Idempotent : un article déjà parsed ne sera plus listé par list_articles_by_status(fetched),
    sauf si reparse=True (rejeu Kafka offset 0).
    """
    if reparse:
        conn.execute(
            """
            UPDATE articles
            SET status = %s,
                silver_s3_uri = %s,
                feed_lang = %s,
                content_lang = %s,
                updated_at = now()
            WHERE url = %s
            """,
            (STATUS_PARSED, silver_s3_uri, feed_lang, content_lang, url),
        )
        return

    conn.execute(
        """
        UPDATE articles
        SET status = %s,
            silver_s3_uri = %s,
            feed_lang = %s,
            content_lang = %s,
            updated_at = now()
        WHERE url = %s AND status = %s
        """,
        (STATUS_PARSED, silver_s3_uri, feed_lang, content_lang, url, STATUS_FETCHED),
    )


def mark_indexed(conn: psycopg.Connection, url: str) -> None:
    """Passe un article en status=indexed après écriture OpenSearch."""
    conn.execute(
        """
        UPDATE articles
        SET status = %s,
            updated_at = now()
        WHERE url = %s AND status = %s
        """,
        (STATUS_INDEXED, url, STATUS_PARSED),
    )


def list_articles_to_embed(
    conn: psycopg.Connection,
    *,
    include_embedded: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Articles prêts pour Qdrant (indexed, ou aussi embedded si re-embed).
    """
    statuses = [STATUS_INDEXED]
    if include_embedded:
        statuses.append(STATUS_EMBEDDED)

    sql = """
        SELECT feed_id, title, url, s3_uri, content_hash, status, silver_s3_uri,
               feed_lang, content_lang
        FROM articles
        WHERE status = ANY(%s)
        ORDER BY fetched_at ASC
    """
    params: list[Any] = [statuses]

    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    return [
        {
            "feed_id": r[0],
            "title": r[1],
            "url": r[2],
            "s3_uri": r[3],
            "content_hash": r[4],
            "status": r[5],
            "silver_s3_uri": r[6],
            "feed_lang": r[7],
            "content_lang": r[8],
        }
        for r in rows
    ]


def mark_embedded(conn: psycopg.Connection, url: str) -> None:
    """Passe un article en status=embedded après écriture Qdrant."""
    conn.execute(
        """
        UPDATE articles
        SET status = %s,
            updated_at = now()
        WHERE url = %s AND status = ANY(%s)
        """,
        (STATUS_EMBEDDED, url, [STATUS_INDEXED, STATUS_EMBEDDED]),
    )


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
