"""Requêtes SQL lecture seule pour l'API catalogue."""

from typing import Any

import psycopg

from presslake.api.schemas import ArticleOut, StatusCount

# Colonnes exposées — une seule source pour list + get.
_ARTICLE_COLUMNS = """
    id, feed_id, url, item_key, content_hash, s3_uri, silver_s3_uri,
    title, published_at, status, fetched_at, updated_at
"""


def _row_to_article(row: tuple[Any, ...]) -> ArticleOut:
    """Mappe une ligne SQL vers le modèle Pydantic."""
    return ArticleOut(
        id=row[0],
        feed_id=row[1],
        url=row[2],
        item_key=row[3],
        content_hash=row[4],
        s3_uri=row[5],
        silver_s3_uri=row[6],
        title=row[7],
        published_at=row[8],
        status=row[9],
        fetched_at=row[10],
        updated_at=row[11],
    )


def _build_filters(
    feed_id: str | None,
    status: str | None,
) -> tuple[str, list[Any]]:
    """Construit la clause WHERE dynamique (paramètres SQL safe)."""
    clauses: list[str] = []
    params: list[Any] = []

    if feed_id is not None:
        clauses.append("feed_id = %s")
        params.append(feed_id)

    if status is not None:
        clauses.append("status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def count_articles_filtered(
    conn: psycopg.Connection,
    *,
    feed_id: str | None = None,
    status: str | None = None,
) -> int:
    """Total pour la pagination (mêmes filtres que list_articles)."""
    where, params = _build_filters(feed_id, status)
    row = conn.execute(f"SELECT count(*) FROM articles {where}", params).fetchone()
    return int(row[0]) if row else 0


def list_articles(
    conn: psycopg.Connection,
    *,
    feed_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ArticleOut]:
    """
    Liste paginée d'articles, triés par fetched_at décroissant.

    limit plafonné côté route (max 200) pour éviter les réponses énormes.
    """
    where, params = _build_filters(feed_id, status)
    params.extend([limit, offset])

    rows = conn.execute(
        f"""
        SELECT {_ARTICLE_COLUMNS}
        FROM articles
        {where}
        ORDER BY fetched_at DESC
        LIMIT %s OFFSET %s
        """,
        params,
    ).fetchall()

    return [_row_to_article(row) for row in rows]


def get_article_by_id(conn: psycopg.Connection, article_id: int) -> ArticleOut | None:
    """Retourne None si l'id n'existe pas (→ HTTP 404)."""
    row = conn.execute(
        f"SELECT {_ARTICLE_COLUMNS} FROM articles WHERE id = %s",
        (article_id,),
    ).fetchone()

    if not row:
        return None

    return _row_to_article(row)


def stats_by_status(conn: psycopg.Connection) -> tuple[int, list[StatusCount]]:
    """Comptage global et par statut pipeline."""
    rows = conn.execute(
        """
        SELECT status, count(*)::int
        FROM articles
        GROUP BY status
        ORDER BY status
        """
    ).fetchall()

    by_status = [StatusCount(status=r[0], count=r[1]) for r in rows]
    total = sum(item.count for item in by_status)
    return total, by_status
