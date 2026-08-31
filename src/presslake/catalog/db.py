"""
Initialisation du schéma catalogue (table articles + migrations).
"""

from pathlib import Path

import psycopg

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def init_schema(conn: psycopg.Connection) -> None:
    """
    Applique schema.sql puis les migrations triées par nom.

    Idempotent : CREATE IF NOT EXISTS + ALTER ADD COLUMN IF NOT EXISTS.
    """
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    if MIGRATIONS_DIR.exists():
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))

    conn.commit()
