"""
Point d'entrée CLI : uv run presslake <commande>

Commandes :
  poll       — ingest RSS + bronze + catalogue
  parse      — bronze → silver
  validate   — JSON Schema (examples | lake)
  serve      — API FastAPI catalogue (lecture seule)
  db init    — schéma Postgres + migrations
"""

import argparse
import sys

from presslake.catalog.db import init_schema
from presslake.contracts.run import run_validate
from presslake.ingest.feeds import load_feeds
from presslake.ingest.poll import poll_all_dedup
from presslake.parse.run import parse_all
from presslake.storage.postgres import get_connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="presslake",
        description="Datalake presse — ingest RSS, lake, RAG sourcé.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("poll", help="Poll RSS → bronze → catalogue.")

    parse_parser = sub.add_parser("parse", help="Parser bronze → silver.")
    parse_parser.add_argument("--limit", type=int, default=None)

    validate_parser = sub.add_parser(
        "validate",
        help="Valider les contrats JSON Schema.",
    )
    validate_parser.add_argument(
        "target",
        choices=["examples", "lake"],
        help="examples = fichiers contracts/examples ; lake = échantillon MinIO.",
    )
    validate_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Nombre d'articles pour validate lake.",
    )

    serve_parser = sub.add_parser(
        "serve",
        help="Démarrer l'API catalogue FastAPI (uvicorn).",
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Rechargement auto du code (dev).",
    )

    db_parser = sub.add_parser("db", help="Opérations base de données.")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init", help="Applique schema.sql + migrations.")

    return parser


def _run_serve(host: str, port: int, reload: bool) -> None:
    """Lance uvicorn sur l'app FastAPI."""
    import uvicorn

    uvicorn.run(
        "presslake.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.command == "poll":
        poll_all_dedup(load_feeds())

    elif args.command == "parse":
        parse_all(limit=args.limit)

    elif args.command == "validate":
        sys.exit(run_validate(target=args.target, limit=args.limit))

    elif args.command == "serve":
        _run_serve(host=args.host, port=args.port, reload=args.reload)

    elif args.command == "db" and args.db_command == "init":
        with get_connection() as conn:
            init_schema(conn)
        print("Schéma catalogue initialisé.")
