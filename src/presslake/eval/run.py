"""Exécution du jeu d'eval RAG."""

from __future__ import annotations

from pathlib import Path

from presslake.eval.dataset import EvalSet, load_eval_set
from presslake.eval.score import CaseScore, score_case
from presslake.eval.tracing import flush_traces
from presslake.rag.chat import answer_question


def run_eval(
    *,
    set_path: Path | str | None = None,
    skip_llm: bool = False,
    limit: int | None = None,
    lang: str | None = None,
) -> tuple[EvalSet, list[CaseScore]]:
    """Enchaîne les cas, score, optionnellement trace (si Langfuse on)."""
    eval_set = load_eval_set(set_path)
    scores: list[CaseScore] = []

    for case in eval_set.cases:
        result = answer_question(
            case.question,
            limit=limit,
            lang=lang,
            skip_llm=skip_llm,
            trace_metadata={
                "eval_set": eval_set.name,
                "eval_case_id": case.id,
                "difficulty": case.difficulty,
                "expect": case.expect,
            },
        )
        scores.append(score_case(case, result, skip_llm=skip_llm))

    flush_traces()
    return eval_set, scores


def format_report(eval_set: EvalSet, scores: list[CaseScore]) -> str:
    passed = sum(1 for s in scores if s.ok)
    lines = [
        f"Eval {eval_set.name} v{eval_set.version} ({eval_set.path})",
        f"{passed}/{len(scores)} OK",
        "",
    ]
    for score in scores:
        mark = "OK" if score.ok else "KO"
        lines.append(
            f"  [{mark}] {score.case_id}  ({score.difficulty}/{score.expect})  "
            f"retrieve={'oui' if score.retrieve_nonempty else 'non'}  "
            f"{score.reason}"
        )
    one_shot = [s for s in scores if s.difficulty == "one_shot"]
    hard = [s for s in scores if s.difficulty == "hard"]
    if one_shot:
        ok_os = sum(1 for s in one_shot if s.ok)
        lines.append(f"\n  one_shot : {ok_os}/{len(one_shot)}")
    if hard:
        ok_h = sum(1 for s in hard if s.ok)
        lines.append(f"  hard     : {ok_h}/{len(hard)}  (ADR 0006 — limite du one-shot)")
    return "\n".join(lines)
