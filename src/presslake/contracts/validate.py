"""
Validation JSON Schema des enveloppes bronze et silver.

Les schémas vivent dans contracts/ à la racine du repo (versionnés git).
docs/contracts/ reste la doc humaine locale ; contracts/*.schema.json est la source de vérité CI.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# Racine repo : src/presslake/contracts/validate.py → parents[3]
CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"

BRONZE_SCHEMA_PATH = CONTRACTS_DIR / "bronze.v1.schema.json"
SILVER_SCHEMA_PATH = CONTRACTS_DIR / "silver.v1.schema.json"


class ContractValidationError(ValueError):
    """Levée quand un objet ne respecte pas le contrat JSON Schema."""


@lru_cache(maxsize=4)
def _load_validator(schema_path: Path) -> Draft202012Validator:
    """Charge et compile un schéma (mis en cache pour perf)."""
    import json

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_bronze(payload: dict[str, Any]) -> None:
    """
    Valide une enveloppe bronze v1.

    Raises:
        ContractValidationError: si un champ manque ou est invalide.
    """
    _validate(payload, BRONZE_SCHEMA_PATH, layer="bronze")


def validate_silver(payload: dict[str, Any]) -> None:
    """
    Valide un document silver v1.

    Raises:
        ContractValidationError: si un champ manque ou est invalide.
    """
    _validate(payload, SILVER_SCHEMA_PATH, layer="silver")


def _validate(payload: dict[str, Any], schema_path: Path, *, layer: str) -> None:
    validator = _load_validator(schema_path)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))

    if not errors:
        return

    messages = []
    for err in errors[:5]:
        path = ".".join(str(p) for p in err.path) or "(racine)"
        messages.append(f"{path}: {err.message}")

    extra = len(errors) - 5
    if extra > 0:
        messages.append(f"… et {extra} autre(s) erreur(s)")

    raise ContractValidationError(
        f"Contrat {layer} invalide ({schema_path.name}):\n  - "
        + "\n  - ".join(messages)
    )


def format_validation_error(err: ValidationError) -> str:
    """Format lisible pour logs / CLI."""
    path = ".".join(str(p) for p in err.path) or "(racine)"
    return f"{path}: {err.message}"
