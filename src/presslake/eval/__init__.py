"""Eval RAG (jeu YAML + scores mécaniques) et traces Langfuse optionnelles."""

from presslake.eval.dataset import EvalCase, EvalSet, load_eval_set
from presslake.eval.score import CaseScore, score_case

__all__ = [
    "CaseScore",
    "EvalCase",
    "EvalSet",
    "load_eval_set",
    "score_case",
]
