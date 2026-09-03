"""
Commande validate : auditer exemples et objets du lake.
"""

import json
from pathlib import Path

import psycopg

from presslake.catalog.articles import list_articles_by_status
from presslake.contracts.validate import (
    ContractValidationError,
    validate_bronze,
    validate_gold,
    validate_silver,
)
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_json_object, get_s3_client, parse_s3_uri

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "contracts" / "examples"


def validate_examples() -> tuple[int, int]:
    """
    Valide les fichiers JSON d'exemple sous contracts/examples/.

    Returns:
        (ok_count, error_count)
    """
    ok = 0
    errors = 0

    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            if path.name.startswith("bronze"):
                validate_bronze(payload)
            elif path.name.startswith("silver"):
                validate_silver(payload)
            elif path.name.startswith("gold"):
                validate_gold(payload)
            else:
                print(f"[SKIP] {path.name} — préfixe inconnu")
                continue
            print(f"[OK] {path.name}")
            ok += 1
        except ContractValidationError as exc:
            print(f"[FAIL] {path.name}\n  {exc}")
            errors += 1

    return ok, errors


def validate_lake(*, limit: int = 10) -> tuple[int, int]:
    """
    Échantillonne le catalogue Postgres et valide bronze + silver dans MinIO.

    Returns:
        (ok_count, error_count)
    """
    ok = 0
    errors = 0
    client = get_s3_client()

    with get_connection() as conn:
        parsed = list_articles_by_status(conn, "parsed", limit=limit)
        fetched = list_articles_by_status(conn, "fetched", limit=limit)
        articles = parsed + fetched

    for article in articles[:limit]:
        bronze_uri = article["s3_uri"]
        try:
            b_bucket, b_key = parse_s3_uri(bronze_uri)
            bronze = get_json_object(client, b_bucket, b_key)
            validate_bronze(bronze)
            print(f"[OK] bronze {article['url'][:60]}…")
            ok += 1
        except (ContractValidationError, OSError, ValueError) as exc:
            print(f"[FAIL] bronze {article.get('url', '?')} — {exc}")
            errors += 1

        silver_uri = article.get("silver_s3_uri")
        if not silver_uri:
            continue

        try:
            s_bucket, s_key = parse_s3_uri(silver_uri)
            silver = get_json_object(client, s_bucket, s_key)
            validate_silver(silver)
            print(f"[OK] silver {article['url'][:60]}…")
            ok += 1
        except (ContractValidationError, OSError, ValueError) as exc:
            print(f"[FAIL] silver {article.get('url', '?')} — {exc}")
            errors += 1

    return ok, errors


def run_validate(*, target: str, limit: int) -> int:
    """
    Point d'entrée CLI validate.

    Returns:
        Code de sortie (0 = succès, 1 = au moins une erreur).
    """
    if target == "examples":
        ok, errors = validate_examples()
    elif target == "lake":
        ok, errors = validate_lake(limit=limit)
    else:
        raise ValueError(f"cible inconnue : {target}")

    print(f"\n→ {ok} OK, {errors} erreur(s)")
    return 1 if errors else 0
