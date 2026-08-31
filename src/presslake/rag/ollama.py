"""Client Ollama (LLM local)."""

import json
from collections.abc import Iterator
from typing import Any

import httpx

from presslake.rag.config import (
    ollama_base_url,
    ollama_keep_alive,
    ollama_model,
    ollama_num_predict,
)


class OllamaError(RuntimeError):
    """Erreur appel Ollama."""


def _chat_payload(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    stream: bool,
    num_predict: int | None = None,
) -> dict[str, Any]:
    return {
        "model": model or ollama_model(),
        "messages": messages,
        "stream": stream,
        "keep_alive": ollama_keep_alive(),
        "options": {
            "num_predict": num_predict if num_predict is not None else ollama_num_predict(),
        },
    }


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    timeout: float = 120.0,
) -> str:
    """
    Appelle Ollama /api/chat (non-streaming).

    Returns:
        Contenu texte de l'assistant.
    """
    payload = _chat_payload(messages, model=model, stream=False)
    url = f"{ollama_base_url()}/api/chat"

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaError(
            f"Ollama inaccessible ({url}) — lancer `ollama serve` et "
            f"`ollama pull {ollama_model()}` : {exc}"
        ) from exc

    data = response.json()
    message = data.get("message") or {}
    content = message.get("content")
    if not content:
        raise OllamaError(f"Réponse Ollama vide : {data!r}")
    return str(content).strip()


def chat_completion_stream(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    timeout: float = 120.0,
) -> Iterator[str]:
    """
    Appelle Ollama /api/chat en streaming (NDJSON).

    Yields:
        Fragments de texte assistant au fur et à mesure.
    """
    payload = _chat_payload(messages, model=model, stream=True)
    url = f"{ollama_base_url()}/api/chat"

    try:
        with httpx.stream("POST", url, json=payload, timeout=timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                message = data.get("message") or {}
                content = message.get("content")
                if content:
                    yield str(content)
                if data.get("done"):
                    break
    except httpx.HTTPError as exc:
        raise OllamaError(
            f"Ollama inaccessible ({url}) — lancer `ollama serve` et "
            f"`ollama pull {ollama_model()}` : {exc}"
        ) from exc


def warmup_ollama(*, timeout: float = 180.0) -> None:
    """
    Charge le modèle Ollama en RAM (1 token) pour éviter la latence au 1er chat.

    Raises:
        OllamaError: si Ollama ne répond pas ou si le modèle est absent.
    """
    payload = _chat_payload(
        [{"role": "user", "content": "ok"}],
        stream=False,
        num_predict=1,
    )
    url = f"{ollama_base_url()}/api/chat"

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaError(
            f"Warmup Ollama échoué ({url}) — `ollama pull {ollama_model()}` : {exc}"
        ) from exc


def check_ollama_available(*, timeout: float = 5.0) -> bool:
    """True si Ollama répond (GET /api/tags)."""
    try:
        response = httpx.get(f"{ollama_base_url()}/api/tags", timeout=timeout)
        return response.status_code == 200
    except httpx.HTTPError:
        return False
