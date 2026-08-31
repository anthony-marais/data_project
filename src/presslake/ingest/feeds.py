"""
Chargement de la configuration des flux RSS.

Ce module ne fait AUCUN appel réseau : il lit uniquement config/feeds.yml
et renvoie des objets Feed typés. C'est la frontière entre la config (YAML)
et le code Python (poll, dédup, etc.).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Feed:
    """
    Représente un flux RSS/Atom configuré dans feeds.yml.

    frozen=True → l'objet est immuable après création (on ne modifie pas
    un feed en cours de poll ; la config vient du fichier).
    """

    id: str  # identifiant court et stable, ex. "france24"
    name: str  # libellé lisible, ex. "France 24"
    url: str  # URL du flux XML
    lang: str  # code langue, ex. "fr"
    category: str  # presse | institution | tech …


# Chemin par défaut : relatif à la racine du repo (là où tu lances uv run).
DEFAULT_FEEDS_PATH = Path("config/feeds.yml")


def load_feeds(path: Path | None = None) -> list[Feed]:
    """
    Lit feeds.yml et renvoie la liste des flux.

    Args:
        path: fichier YAML à lire. Si None, utilise config/feeds.yml.

    Returns:
        Liste d'objets Feed, un par entrée sous la clé "feeds:" du YAML.

    Raises:
        FileNotFoundError: si le fichier n'existe pas.
        KeyError: si la structure YAML n'a pas de clé "feeds".
    """
    path = path or DEFAULT_FEEDS_PATH

    # read_text + utf-8 : gère les accents (Le Monde, RFI, etc.)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Chaque row est un dict {"id": ..., "name": ..., ...}
    # Feed(**row) déplie le dict en arguments du constructeur.
    return [Feed(**row) for row in raw["feeds"]]
