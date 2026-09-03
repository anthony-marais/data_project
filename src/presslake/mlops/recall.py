"""Recall@k sur le jeu d'eval (cas grounded) — métrique d'expérience embedding."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from presslake.eval.dataset import EvalSet, load_eval_set
from presslake.mlops.params import PARAMS_PATH, load_embed_params
from presslake.rag.config import rag_top_k
from presslake.vector.config import embedding_model, embedding_vector_size

_REPO = Path(__file__).resolve().parents[3]
METRICS_PATH = _REPO / "metrics" / "embed-recall.json"


@dataclass(frozen=True)
class RecallReport:
    model: str
    vector_size: int
    k: int
    eval_set: str
    n_grounded: int
    n_hits: int
    recall_at_k: float
    n_refuse: int
    n_refuse_ok: int
    hits: tuple[str, ...]
    misses: tuple[str, ...]

    def as_metrics_dict(self) -> dict:
        return {
            "model": self.model,
            "vector_size": self.vector_size,
            "k": self.k,
            "eval_set": self.eval_set,
            "recall_at_k": self.recall_at_k,
            "n_grounded": self.n_grounded,
            "n_hits": self.n_hits,
            "n_refuse": self.n_refuse,
            "n_refuse_ok": self.n_refuse_ok,
        }


def recall_at_k_from_flags(hits: list[bool], *, k: int) -> float:
    """Recall@k = fraction de cas grounded avec ≥1 passage (k documenté, pas dans le calcul)."""
    del k
    if not hits:
        return 0.0
    return sum(1 for h in hits if h) / len(hits)


def evaluate_recall(
    *,
    k: int | None = None,
    set_path: Path | str | None = None,
    retrieve: Callable[..., list] | None = None,
) -> RecallReport:
    """
    grounded : hit si retrieve non vide.
    refuse   : ok si retrieve vide (même logique eval --skip-llm hors LLM).
    """
    from presslake.retrieve.hybrid import retrieve_passages

    retrieve_fn = retrieve or retrieve_passages
    top_k = k if k is not None else int(load_embed_params().get("top_k") or rag_top_k())
    eval_set: EvalSet = load_eval_set(set_path)

    grounded_hits: list[bool] = []
    hit_ids: list[str] = []
    miss_ids: list[str] = []
    refuse_ok = 0
    n_refuse = 0

    for case in eval_set.cases:
        passages = retrieve_fn(case.question, limit=top_k)
        nonempty = bool(passages)
        if case.expect == "grounded":
            grounded_hits.append(nonempty)
            if nonempty:
                hit_ids.append(case.id)
            else:
                miss_ids.append(case.id)
        else:
            n_refuse += 1
            if not nonempty:
                refuse_ok += 1

    n_g = len(grounded_hits)
    n_hits = sum(1 for h in grounded_hits if h)
    return RecallReport(
        model=embedding_model(),
        vector_size=embedding_vector_size(),
        k=top_k,
        eval_set=eval_set.name,
        n_grounded=n_g,
        n_hits=n_hits,
        recall_at_k=recall_at_k_from_flags(grounded_hits, k=top_k),
        n_refuse=n_refuse,
        n_refuse_ok=refuse_ok,
        hits=tuple(hit_ids),
        misses=tuple(miss_ids),
    )


def write_metrics(report: RecallReport, path: Path | None = None) -> Path:
    dest = path or METRICS_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(report.as_metrics_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return dest


def format_report(report: RecallReport) -> str:
    lines = [
        f"Recall@{report.k}  {report.n_hits}/{report.n_grounded} = {report.recall_at_k:.3f}",
        f"modèle     {report.model}",
        f"dim        {report.vector_size}",
        f"eval       {report.eval_set}",
        f"refuse OK  {report.n_refuse_ok}/{report.n_refuse} (retrieve vide)",
        f"params     {PARAMS_PATH.name}",
    ]
    if report.misses:
        lines.append("misses     " + ", ".join(report.misses))
    return "\n".join(lines)
