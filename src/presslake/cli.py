"""
Point d'entrée CLI : uv run presslake <commande>

Aujourd'hui une seule commande : poll
Demain : d'autres sous-commandes (parse, index, etc.) s'ajouteront ici.
"""

import argparse

from presslake.ingest.feeds import load_feeds
from presslake.ingest.poll import poll_all_dedup


def build_parser() -> argparse.ArgumentParser:
    """
    Construit l'arbre argparse.

    Structure :
      presslake poll   → lance l'ingest RSS avec dédup
    """
    parser = argparse.ArgumentParser(
        prog="presslake",
        description="Datalake presse — ingest RSS, lake, RAG sourcé.",
    )

    # Sous-commandes obligatoires : force l'utilisateur à taper « poll », pas juste « presslake ».
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "poll",
        help="Interroge les flux RSS configurés (config/feeds.yml) et affiche les nouveaux items.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """
    Fonction appelée par pyproject.toml → [project.scripts] presslake = presslake:main

    Args:
        argv: arguments CLI (None = sys.argv). Utile pour les tests.
    """
    args = build_parser().parse_args(argv)

    if args.command == "poll":
        # 1. Config YAML → objets Feed
        feeds = load_feeds()
        # 2. Fetch + parse + dédup + sauvegarde seen.json
        poll_all_dedup(feeds)
