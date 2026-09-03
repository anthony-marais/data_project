"""Scores mécaniques — reproductibles, sans second LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass

from presslake.eval.dataset import EvalCase
from presslake.rag.chat import ChatAnswer
from presslake.rag.prompt import REFUSAL_MESSAGE

_CITE_RE = re.compile(r"\[1\]")


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    difficulty: str
    expect: str
    ok: bool
    retrieve_nonempty: bool
    refused: bool
    has_citation: bool
    reason: str


def _has_citation(answer: str) -> bool:
    return bool(_CITE_RE.search(answer)) or "Sources PressLake" in answer


def score_case(case: EvalCase, result: ChatAnswer, *, skip_llm: bool) -> CaseScore:
    """
    grounded : au moins un passage ; si LLM appelé, pas de refus + une citation [1].
    refuse   : retrieve vide ou refus explicite.
    """
    retrieve_nonempty = bool(result.passages)
    refused = result.refused or result.answer.strip() == REFUSAL_MESSAGE.strip()
    has_citation = _has_citation(result.answer)

    if case.expect == "refuse":
        ok = (not retrieve_nonempty) or refused
        reason = (
            "refus / hors corpus OK"
            if ok
            else "retrieve a trouvé des passages (entité du corpus ou BM25) — pas un hors-sujet"
        )
    else:
        if not retrieve_nonempty:
            ok = False
            reason = "retrieve vide (indexer + embed le corpus, ou question trop loin)"
        elif skip_llm:
            ok = True
            reason = "passages trouvés (retrieve seul)"
        elif refused:
            ok = False
            reason = "refus alors que des passages existent"
        elif not has_citation:
            ok = False
            reason = "pas de citation [1] / footer Sources PressLake"
        else:
            ok = True
            reason = "grounded + citation"

    return CaseScore(
        case_id=case.id,
        difficulty=case.difficulty,
        expect=case.expect,
        ok=ok,
        retrieve_nonempty=retrieve_nonempty,
        refused=refused,
        has_citation=has_citation,
        reason=reason,
    )
