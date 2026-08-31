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
