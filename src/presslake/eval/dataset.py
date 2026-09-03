"""Chargement du jeu d'eval YAML."""

from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVAL_SET = _REPO_ROOT / "config" / "eval" / "rag-v1.yml"


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    expect: str  # grounded | refuse
    difficulty: str  # one_shot | hard


@dataclass(frozen=True)
class EvalSet:
    name: str
    version: int
    cases: tuple[EvalCase, ...]
    path: Path


def load_eval_set(path: Path | str | None = None) -> EvalSet:
    """Charge `config/eval/rag-v1.yml` (ou un autre fichier)."""
    file_path = Path(path) if path is not None else DEFAULT_EVAL_SET
    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Jeu d'eval invalide (racine) : {file_path}")

    cases: list[EvalCase] = []
    for item in raw.get("cases") or []:
        expect = str(item.get("expect", "")).strip()
        difficulty = str(item.get("difficulty", "one_shot")).strip()
        if expect not in {"grounded", "refuse"}:
            raise ValueError(f"expect inconnu pour {item.get('id')!r} : {expect}")
        if difficulty not in {"one_shot", "hard"}:
            raise ValueError(
                f"difficulty inconnue pour {item.get('id')!r} : {difficulty}"
            )
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"question vide pour {item.get('id')!r}")
        cases.append(
            EvalCase(
                id=str(item["id"]),
                question=question,
                expect=expect,
                difficulty=difficulty,
            )
        )
    if not cases:
        raise ValueError(f"Aucun cas dans {file_path}")

    return EvalSet(
        name=str(raw.get("name") or file_path.stem),
        version=int(raw.get("version") or 1),
        cases=tuple(cases),
        path=file_path,
    )
