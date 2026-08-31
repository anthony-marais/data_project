"""Requêtes Postgres partagées pour observabilité (catalogue)."""

import os
from datetime import datetime

import psycopg


def stale_threshold_seconds() -> int:
    """Seuil alerte : PRESSLAKE_STALE_HOURS (défaut 6) converti en secondes."""
    hours = float(os.environ.get("PRESSLAKE_STALE_HOURS", "6"))
    return int(hours * 3600)


def get_last_write_at(conn: psycopg.Connection) -> datetime | None:
    """Dernière activité ingest : max(fetched_at) dans articles."""
    row = conn.execute("SELECT max(fetched_at) FROM articles").fetchone()
    if not row or row[0] is None:
        return None
    return row[0]


def get_articles_total(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM articles").fetchone()
    return int(row[0]) if row else 0
