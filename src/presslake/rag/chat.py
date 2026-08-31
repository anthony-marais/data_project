"""Orchestration RAG one-shot : retrieve → prompt → Ollama."""

from collections.abc import Iterator
from dataclasses import dataclass

from presslake.rag.ollama import OllamaError, chat_completion, chat_completion_stream
from presslake.rag.prompt import (
    REFUSAL_MESSAGE,
    build_chat_messages,
    format_sources_footer,
)
from presslake.retrieve.hybrid import retrieve_passages
from presslake.retrieve.types import RetrievedPassage


@dataclass
class ChatAnswer:
    """Réponse RAG avec passages sources."""

    question: str
    answer: str
    passages: list[RetrievedPassage]
    refused: bool = False
    model: str | None = None


def answer_question(
    question: str,
    *,
    limit: int | None = None,
    lang: str | None = None,
    skip_llm: bool = False,
) -> ChatAnswer:
    """
    Retrieve hybride + génération Ollama (ou refus si corpus vide).

    Args:
        skip_llm: si True, retourne seulement les passages (debug retrieve).
    """
    from presslake.rag.config import ollama_model, rag_top_k

    top_k = limit if limit is not None else rag_top_k()
    passages = retrieve_passages(question, limit=top_k, lang=lang)

    if not passages:
        return ChatAnswer(
            question=question,
            answer=REFUSAL_MESSAGE,
            passages=[],
            refused=True,
        )

    if skip_llm:
        preview = "\n".join(
            f"[{i}] {p.citation_label()}" for i, p in enumerate(passages, start=1)
        )
        return ChatAnswer(
            question=question,
            answer=f"(retrieve seul)\n{preview}",
            passages=passages,
        )

    messages = build_chat_messages(question, passages)
    try:
        raw_answer = chat_completion(messages)
    except OllamaError:
        raise

    full_answer = raw_answer + format_sources_footer(passages)
    return ChatAnswer(
        question=question,
        answer=full_answer,
        passages=passages,
        model=ollama_model(),
    )


def iter_answer_text(
    question: str,
    *,
    limit: int | None = None,
    lang: str | None = None,
) -> Iterator[str]:
    """
    Même pipeline que answer_question, mais yield le texte token par token.

    Le retrieve et le footer sources sont émis en une fois ; seul le corps
    LLM est streamé depuis Ollama.
    """
    from presslake.rag.config import rag_top_k

    top_k = limit if limit is not None else rag_top_k()
    passages = retrieve_passages(question, limit=top_k, lang=lang)

    if not passages:
        yield REFUSAL_MESSAGE
        return

    messages = build_chat_messages(question, passages)
    yield from chat_completion_stream(messages)

    footer = format_sources_footer(passages)
    if footer:
        yield footer
