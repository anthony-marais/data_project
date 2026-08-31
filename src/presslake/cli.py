"""
Point d'entrée CLI : uv run presslake <commande>

Commandes :
  poll     — ingest RSS + bronze MinIO + catalogue Postgres
  db init  — crée la table articles (schéma module 04)
"""

import argparse

from presslake.catalog.db import init_schema
from presslake.ingest.feeds import load_feeds
from presslake.ingest.poll import poll_all_dedup
from presslake.storage.postgres import get_connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="presslake",
        description="Datalake presse — ingest RSS, lake, RAG sourcé.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "poll",
        help="Poll RSS → bronze MinIO → catalogue Postgres (dédup).",
    )

    db_parser = sub.add_parser("db", help="Opérations base de données.")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init", help="Applique schema.sql (table articles).")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.command == "poll":
        feeds = load_feeds()
        poll_all_dedup(feeds)

    elif args.command == "db" and args.db_command == "init":
        with get_connection() as conn:
            init_schema(conn)
        print("Schéma catalogue initialisé (table articles).")
