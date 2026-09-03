"""Baseline embedding git + registre local pour rollback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from presslake.mlops.recall import RecallReport

_REPO = Path(__file__).resolve().parents[3]
REGISTRY_PATH = _REPO / "config" / "embed-registry.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    file_path = path or REGISTRY_PATH
    return json.loads(file_path.read_text(encoding="utf-8"))


def register_report(report: RecallReport, path: Path | None = None) -> Path:
    dest = path or REGISTRY_PATH
    payload = {
        "model": report.model,
        "vector_size": report.vector_size,
        "k": report.k,
        "recall_at_k": report.recall_at_k,
        "eval_set": report.eval_set,
        "note": "Écrit par presslake recall --register",
    }
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def rollback_instructions(path: Path | None = None) -> str:
    reg = load_registry(path)
    model = reg.get("model") or ""
    size = reg.get("vector_size") or 384
    return (
        "Rollback embedding (remettre le registre, puis ré-embed) :\n"
        f"  1. Dans .env / params.yaml : EMBEDDING_MODEL={model}\n"
        f"  2. EMBEDDING_VECTOR_SIZE={size}  (et embed.vector_size dans params.yaml)\n"
        "  3. uv run presslake embed --recreate\n"
        "  4. uv run presslake recall\n"
        f"Registre : {path or REGISTRY_PATH}\n"
        f"recall_at_k enregistré : {reg.get('recall_at_k')!r}"
    )
