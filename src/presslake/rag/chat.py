"""Orchestration RAG one-shot : retrieve → prompt → Ollama."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from presslake.rag.ollama import chat_completion, chat_completion_stream
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
    trace_metadata: dict[str, Any] | None = None,
) -> ChatAnswer:
    """
    Retrieve hybride + génération Ollama (ou refus si corpus vide).

    Args:
        skip_llm: si True, retourne seulement les passages (debug retrieve).
        trace_metadata: tags Langfuse (ex. eval_case_id) si tracing activé.
    """
    from presslake.eval.tracing import rag_observation
    from presslake.rag.config import ollama_model, rag_top_k

    top_k = limit if limit is not None else rag_top_k()

    with rag_observation(
        name="presslake.chat",
        question=question,
        metadata=trace_metadata,
    ) as span:
        passages = retrieve_passages(question, limit=top_k, lang=lang)
        span.update_retrieve(passages)

        if not passages:
            span.update_output(output=REFUSAL_MESSAGE, refused=True, skip_llm=skip_llm)
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
            answer = f"(retrieve seul)\n{preview}"
            span.update_output(output=answer, refused=False, skip_llm=True)
            return ChatAnswer(
                question=question,
                answer=answer,
                passages=passages,
            )

        messages = build_chat_messages(question, passages)
        raw_answer = chat_completion(messages)

        full_answer = raw_answer + format_sources_footer(passages)
        span.update_output(
            output=full_answer,
            refused=False,
            skip_llm=False,
            model=ollama_model(),
        )
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
    LLM est streamé depuis Ollama. Trace Langfuse à la fin du flux.
    """
    from presslake.eval.tracing import rag_observation
    from presslake.rag.config import ollama_model, rag_top_k

    top_k = limit if limit is not None else rag_top_k()
    chunks: list[str] = []

    with rag_observation(name="presslake.chat.stream", question=question) as span:
        passages = retrieve_passages(question, limit=top_k, lang=lang)
        span.update_retrieve(passages)

        if not passages:
            span.update_output(output=REFUSAL_MESSAGE, refused=True, stream=True)
            yield REFUSAL_MESSAGE
            return

        messages = build_chat_messages(question, passages)
        for piece in chat_completion_stream(messages):
            chunks.append(piece)
            yield piece

        footer = format_sources_footer(passages)
        if footer:
            chunks.append(footer)
            yield footer

        span.update_output(
            output="".join(chunks),
            refused=False,
            stream=True,
            model=ollama_model(),
        )
