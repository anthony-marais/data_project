"""Lecture params.yaml (DVC) — override par variables d'environnement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[3]
PARAMS_PATH = _REPO / "params.yaml"


def load_embed_params() -> dict[str, Any]:
    if not PARAMS_PATH.is_file():
        return {}
    raw = yaml.safe_load(PARAMS_PATH.read_text(encoding="utf-8")) or {}
    embed = raw.get("embed") or {}
    return embed if isinstance(embed, dict) else {}
