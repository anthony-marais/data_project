"""Traces Langfuse optionnelles — no-op si clés absentes ou tracing off."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv

from presslake.retrieve.types import RetrievedPassage

logger = logging.getLogger(__name__)

load_dotenv()


def tracing_enabled() -> bool:
    """True seulement avec clés + URL locales et flag explicite."""
    flag = os.environ.get("LANGFUSE_TRACING_ENABLED", "false").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return False
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
        and os.environ.get("LANGFUSE_BASE_URL", "").strip()
    )


@contextmanager
def rag_observation(
    *,
    name: str,
    question: str,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Span Langfuse autour d'un tour RAG ; no-op sinon."""
    if not tracing_enabled():
        yield _NoopSpan()
        return

    try:
        from langfuse import get_client
    except ImportError:
        logger.warning("Package langfuse absent — traces désactivées")
        yield _NoopSpan()
        return

    client = get_client()
    extra = dict(metadata or {})
    extra["product"] = "presslake"
    try:
        with client.start_as_current_observation(
            as_type="span",
            name=name,
            input=question,
            metadata=extra,
        ) as span:
            yield _LangfuseSpan(span)
    except Exception:
        logger.exception("Langfuse indisponible — le chat continue sans trace")
        yield _NoopSpan()


def flush_traces() -> None:
    if not tracing_enabled():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.debug("flush Langfuse ignoré", exc_info=True)


class _NoopSpan:
    def update_retrieve(self, passages: list[RetrievedPassage]) -> None:
        return None

    def update_output(self, **kwargs: Any) -> None:
        return None


class _LangfuseSpan:
    def __init__(self, span: Any) -> None:
        self._span = span

    def update_retrieve(self, passages: list[RetrievedPassage]) -> None:
        self._span.update(
            metadata={
                "n_passages": len(passages),
                "sources": [p.citation_label() for p in passages[:8]],
            }
        )

    def update_output(self, **kwargs: Any) -> None:
        output = kwargs.pop("output", None)
        self._span.update(output=output, metadata=kwargs)
