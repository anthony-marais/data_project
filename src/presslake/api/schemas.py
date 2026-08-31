"""Modèles Pydantic exposés par l'API catalogue."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArticleOut(BaseModel):
    """
    Représentation publique d'un article catalogue.

    Correspond aux colonnes Postgres `articles` (lecture seule).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    feed_id: str
    url: str
    item_key: str
    content_hash: str
    s3_uri: str
    silver_s3_uri: str | None = None
    title: str | None = None
    published_at: datetime | None = None
    status: str
    fetched_at: datetime
    updated_at: datetime


class ArticleListOut(BaseModel):
    """Réponse paginée GET /articles."""

    total: int = Field(description="Nombre total d'articles (filtres appliqués)")
    limit: int
    offset: int
    items: list[ArticleOut]


class StatusCount(BaseModel):
    """Une ligne de GET /stats."""

    status: str
    count: int


class StatsOut(BaseModel):
    """Comptage par statut pipeline."""

    total: int
    by_status: list[StatusCount]


class HealthOut(BaseModel):
    """GET /health."""

    status: str = "ok"
    service: str = "presslake-catalog"


class OpsStatusOut(BaseModel):
    """GET /ops/status — surveillance worker ingest."""

    last_write_at: datetime | None
    seconds_since_write: int | None
    stale_threshold_seconds: int
    stale: bool
    articles_total: int
    message: str


class RetrievedPassageOut(BaseModel):
    """Passage retrievé (hybride BM25 + vecteurs)."""

    text: str
    score: float = Field(description="Score RRF après fusion (comparer dans une même requête)")
    sources: list[str] = Field(description="Moteurs ayant contribué : bm25, vector")
    content_hash: str | None = None
    chunk_index: int | None = None
    feed_id: str | None = None
    title: str | None = None
    content_lang: str | None = None
    canonical_url: str | None = None
    silver_s3_uri: str | None = None


class RetrieveOut(BaseModel):
    """GET /retrieve — retrieve hybride one-shot."""

    query: str
    limit: int
    passages: list[RetrievedPassageOut]


class ChatRequest(BaseModel):
    """POST /chat — RAG one-shot (JSON simple, hors OpenAI-compat)."""

    message: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=20)
    lang: str | None = Field(default=None, pattern="^(fr|en)$")


class ChatResponse(BaseModel):
    """Réponse POST /chat."""

    message: str
    answer: str
    refused: bool
    model: str | None = None
    passages: list[RetrievedPassageOut]
