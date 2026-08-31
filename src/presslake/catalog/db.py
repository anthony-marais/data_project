"""
Initialisation du schéma catalogue (table articles).
"""

from pathlib import Path

import psycopg

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_schema(conn: psycopg.Connection) -> None:
    """
    Exécute schema.sql (CREATE TABLE IF NOT EXISTS …).

    Idempotent : safe à relancer (db init plusieurs fois).
    """
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.execute(sql)
    conn.commit()
