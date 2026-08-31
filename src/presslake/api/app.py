"""
Application FastAPI — catalogue PressLake (lecture seule).

Lancer : uv run presslake serve
Docs   : http://localhost:8000/docs
"""

from fastapi import Depends, FastAPI, HTTPException, Query
import psycopg

from presslake.api.deps import get_db
from presslake.api.queries import (
    count_articles_filtered,
    get_article_by_id,
    list_articles,
    stats_by_status,
)
from presslake.api.schemas import ArticleListOut, ArticleOut, HealthOut, StatsOut

# Limite max pour éviter de charger tout le catalogue d'un coup.
MAX_PAGE_SIZE = 200


def create_app() -> FastAPI:
    """Fabrique l'app (utile pour tests et uvicorn)."""
    app = FastAPI(
        title="PressLake Catalogue API",
        description=(
            "API lecture seule sur le catalogue Postgres. "
            "Expose inventaire articles, statuts pipeline, pointeurs MinIO."
        ),
        version="0.1.0",
    )

    @app.get("/health", response_model=HealthOut, tags=["ops"])
    def health() -> HealthOut:
        """Santé du service (ne vérifie pas Postgres — endpoint léger)."""
        return HealthOut()

    @app.get("/articles", response_model=ArticleListOut, tags=["catalog"])
    def get_articles(
        feed_id: str | None = Query(default=None, description="Filtrer par flux RSS"),
        status: str | None = Query(
            default=None,
            description="Filtrer par statut (fetched, parsed, …)",
        ),
        limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
        conn: psycopg.Connection = Depends(get_db),
    ) -> ArticleListOut:
        """
        Liste paginée des articles du catalogue.

        Tri : plus récemment ingérés en premier (`fetched_at DESC`).
        """
        total = count_articles_filtered(conn, feed_id=feed_id, status=status)
        items = list_articles(
            conn,
            feed_id=feed_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return ArticleListOut(total=total, limit=limit, offset=offset, items=items)

    @app.get("/articles/{article_id}", response_model=ArticleOut, tags=["catalog"])
    def get_article(
        article_id: int,
        conn: psycopg.Connection = Depends(get_db),
    ) -> ArticleOut:
        """Détail d'un article par id Postgres (BIGSERIAL)."""
        article = get_article_by_id(conn, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article introuvable")
        return article

    @app.get("/stats", response_model=StatsOut, tags=["catalog"])
    def get_stats(conn: psycopg.Connection = Depends(get_db)) -> StatsOut:
        """Comptage des articles par statut pipeline."""
        total, by_status = stats_by_status(conn)
        return StatsOut(total=total, by_status=by_status)

    return app


# Instance importée par uvicorn : presslake.api.app:app
app = create_app()
