"""
Connexion PostgreSQL.

DATABASE_URL dans .env, ex. :
  postgresql://presslake:secret@localhost:5432/presslake
"""

import os
from functools import lru_cache

import psycopg
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_database_url() -> str:
    """
    URL de connexion Postgres.

    Priorité :
      1. DATABASE_URL dans .env
      2. Construite depuis POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB

    Raises:
        RuntimeError: si aucune config disponible
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    if user and password and db:
        return f"postgresql://{user}:{password}@localhost:5432/{db}"

    raise RuntimeError(
        "DATABASE_URL ou POSTGRES_USER/PASSWORD/DB manquants dans .env"
    )


def get_connection() -> psycopg.Connection:
    """
    Ouvre une connexion psycopg (context manager recommandé).

    Usage:
        with get_connection() as conn:
            conn.execute(...)
            conn.commit()
    """
    return psycopg.connect(get_database_url())
