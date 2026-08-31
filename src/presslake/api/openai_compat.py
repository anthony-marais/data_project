"""Route OpenAI-compatible pour Open WebUI / LibreChat."""

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from presslake.rag.chat import answer_question, iter_answer_text
from presslake.rag.config import openai_compat_model_name
from presslake.rag.ollama import OllamaError

router = APIRouter(prefix="/v1", tags=["openai-compat"])


class ChatMessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="presslake-rag")
    messages: list[ChatMessageIn]
    stream: bool = False
    temperature: float | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessageIn
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]


def _last_user_message(messages: list[ChatMessageIn]) -> str:
    for message in reversed(messages):
        if message.role == "user" and message.content.strip():
            return message.content.strip()
    raise HTTPException(status_code=400, detail="Aucun message user dans la requête.")


def _sse_chat_stream(question: str) -> Iterator[str]:
    """Événements SSE OpenAI (chat.completion.chunk)."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_name = openai_compat_model_name()

    def event(delta: dict[str, Any], finish_reason: str | None = None) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    first_chunk = True
    try:
        for text in iter_answer_text(question):
            if first_chunk:
                yield event({"role": "assistant", "content": ""})
                first_chunk = False
            yield event({"content": text})
    except OllamaError as exc:
        if first_chunk:
            yield event({"role": "assistant", "content": ""})
        yield event({"content": str(exc)})

    yield event({}, finish_reason="stop")
    yield "data: [DONE]\n\n"


@router.post("/chat/completions", response_model=None)
def openai_chat_completions(
    body: ChatCompletionRequest,
) -> ChatCompletionResponse | StreamingResponse:
    """
    API OpenAI-compatible — point d'entrée Open WebUI / LibreChat.

    PressLake injecte le retrieve RAG puis appelle Ollama en local.
    Le champ `model` du client est ignoré (sauf affichage) ; le modèle réel = `OLLAMA_MODEL`.
    """
    question = _last_user_message(body.messages)

    if body.stream:
        return StreamingResponse(
            _sse_chat_stream(question),
            media_type="text/event-stream",
        )

    try:
        result = answer_question(question)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    model_name = openai_compat_model_name()
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        created=int(time.time()),
        model=model_name,
        choices=[
            ChatCompletionChoice(
                message=ChatMessageIn(role="assistant", content=result.answer),
            )
        ],
    )


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "presslake"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelCard]


@router.get("/models", response_model=ModelListResponse)
def openai_list_models() -> ModelListResponse:
    """Liste des modèles exposés (requis par certaines UI)."""
    name = openai_compat_model_name()
    return ModelListResponse(data=[ModelCard(id=name)])
