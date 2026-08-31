"""
Persistance des articles déjà vus (déduplication).

Module 02 : on stocke localement dans data/seen.json.
Module 03+ : le bronze MinIO et le catalogue Postgres prendront le relais,
mais seen.json reste utile pour éviter de re-traiter les mêmes items à chaque poll.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# Fichier créé au premier poll ; gitignoré (état local, pas du code).
DEFAULT_SEEN_PATH = Path("data/seen.json")


def load_seen(path: Path = DEFAULT_SEEN_PATH) -> dict[str, str]:
    """
    Charge l'ensemble des clés déjà ingérées.

    Returns:
        Dict { "feed_id:item_key": "2026-08-31T12:00:00+00:00", ... }
        Dict vide si le fichier n'existe pas encore (premier lancement).
    """
    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def save_seen(seen: dict[str, str], path: Path = DEFAULT_SEEN_PATH) -> None:
    """
    Sauvegarde l'état seen sur disque.

    mkdir(parents=True) crée data/ si absent.
    ensure_ascii=False préserve les caractères accentués dans les clés (URLs).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(seen, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def mark_seen(seen: dict[str, str], key: str) -> bool:
    """
    Enregistre une clé comme « déjà vue ».

    Args:
        seen: dict modifié en place (chargé par load_seen).
        key: clé composite, ex. "france24:abc-123-guid".

    Returns:
        True  → la clé existait déjà (doublon, on ignore l'item).
        False → nouvelle clé, timestamp UTC ajouté.
    """
    if key in seen:
        return True

    # ISO 8601 en UTC : traçabilité de quand l'item a été vu pour la 1ère fois.
    seen[key] = datetime.now(timezone.utc).isoformat()
    return False
