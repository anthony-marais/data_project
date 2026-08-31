"""
Point d'entrée CLI : uv run presslake <commande>
"""

import argparse
import sys

from presslake.catalog.db import init_schema
from presslake.contracts.run import run_validate
from presslake.ingest.feeds import load_feeds
from presslake.ingest.poll import poll_all_dedup
from presslake.observability.alerts import evaluate_ops_status
from presslake.parse.run import parse_all, parse_from_kafka
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
    parse_parser.add_argument(
        "--from-kafka",
        action="store_true",
        help="Consommer presslake.articles.ingested au lieu du catalogue.",
    )
    parse_parser.add_argument(
        "--replay",
        action="store_true",
        help="Rejeu depuis l'offset 0 (avec --from-kafka).",
    )

    validate_parser = sub.add_parser("validate", help="Valider les contrats JSON Schema.")
    validate_parser.add_argument("target", choices=["examples", "lake"])
    validate_parser.add_argument("--limit", type=int, default=10)

    serve_parser = sub.add_parser("serve", help="API FastAPI + /metrics.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    ops_parser = sub.add_parser("ops", help="Surveillance ops.")
    ops_sub = ops_parser.add_subparsers(dest="ops_command", required=True)
    ops_sub.add_parser("status", help="Dernière écriture + alerte 6 h.")

    db_parser = sub.add_parser("db", help="Opérations base de données.")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init", help="Applique schema.sql + migrations.")

    return parser


def _run_serve(host: str, port: int, reload: bool) -> None:
    import uvicorn

    uvicorn.run("presslake.api.app:app", host=host, port=port, reload=reload)


def _run_ops_status() -> int:
    """Affiche l'état ops ; code 1 si stale (pour scripts cron)."""
    with get_connection() as conn:
        status = evaluate_ops_status(conn)

    print(status.message)
    if status.last_write_at:
        print(f"Dernière écriture : {status.last_write_at.isoformat()}")
        print(f"Il y a            : {status.seconds_since_write // 3600}h {(status.seconds_since_write % 3600) // 60}min")
    print(f"Articles          : {status.articles_total}")
    print(f"Stale             : {status.stale}")

    return 1 if status.stale else 0


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.command == "poll":
        poll_all_dedup(load_feeds())

    elif args.command == "parse":
        if args.replay and not args.from_kafka:
            print("Erreur : --replay nécessite --from-kafka.", file=sys.stderr)
            sys.exit(2)
        if args.from_kafka:
            parse_from_kafka(replay=args.replay, limit=args.limit)
        else:
            parse_all(limit=args.limit)

    elif args.command == "validate":
        sys.exit(run_validate(target=args.target, limit=args.limit))

    elif args.command == "serve":
        _run_serve(host=args.host, port=args.port, reload=args.reload)

    elif args.command == "ops" and args.ops_command == "status":
        sys.exit(_run_ops_status())

    elif args.command == "db" and args.db_command == "init":
        with get_connection() as conn:
            init_schema(conn)
        print("Schéma catalogue initialisé.")
