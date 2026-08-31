"""Dépendances FastAPI (connexion Postgres par requête)."""

from collections.abc import Generator

import psycopg

from presslake.storage.postgres import get_connection


def get_db() -> Generator[psycopg.Connection, None, None]:
    """
    Fournit une connexion Postgres au handler, fermée automatiquement.

    Pattern FastAPI standard : yield dans une dépendance.
    """
    with get_connection() as conn:
        yield conn
