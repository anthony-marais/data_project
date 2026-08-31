"""
Application FastAPI — catalogue PressLake (lecture seule).

Lancer : uv run presslake serve
Docs   : http://localhost:8000/docs
Métriques : http://localhost:8000/metrics
"""

from fastapi import Depends, FastAPI, HTTPException, Query, Response
import psycopg
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from presslake.api.deps import get_db
from presslake.api.queries import (
    count_articles_filtered,
    get_article_by_id,
    list_articles,
    stats_by_status,
)
from presslake.api.schemas import (
    ArticleListOut,
    ArticleOut,
    HealthOut,
    OpsStatusOut,
    StatsOut,
)
from presslake.observability.alerts import evaluate_ops_status
from presslake.observability.catalog_metrics import refresh_metrics_from_postgres

MAX_PAGE_SIZE = 200


def create_app() -> FastAPI:
    """Fabrique l'app (utile pour tests et uvicorn)."""
    app = FastAPI(
        title="PressLake Catalogue API",
        description=(
            "API lecture seule sur le catalogue Postgres. "
            "Expose inventaire articles, statuts pipeline, pointeurs MinIO, métriques ops."
        ),
        version="0.1.0",
    )

    @app.get("/health", response_model=HealthOut, tags=["ops"])
    def health() -> HealthOut:
        """Santé du service (ne vérifie pas Postgres — endpoint léger)."""
        return HealthOut()

    @app.get("/metrics", tags=["ops"])
    def metrics(conn: psycopg.Connection = Depends(get_db)) -> Response:
        """
        Métriques Prometheus.

        Les jauges catalogue et worker sont rafraîchies depuis Postgres à chaque
        scrape (persistant même si poll/parse tournent en CLI séparée).
        """
        refresh_metrics_from_postgres(conn)
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/ops/status", response_model=OpsStatusOut, tags=["ops"])
    def ops_status(conn: psycopg.Connection = Depends(get_db)) -> OpsStatusOut:
        """
        État ops : dernière écriture catalogue + alerte si > 6 h sans write.

        Seuil configurable via PRESSLAKE_STALE_HOURS (défaut 6).
        """
        status = evaluate_ops_status(conn)
        return OpsStatusOut(
            last_write_at=status.last_write_at,
            seconds_since_write=status.seconds_since_write,
            stale_threshold_seconds=status.stale_threshold_seconds,
            stale=status.stale,
            articles_total=status.articles_total,
            message=status.message,
        )

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
        article = get_article_by_id(conn, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article introuvable")
        return article

    @app.get("/stats", response_model=StatsOut, tags=["catalog"])
    def get_stats(conn: psycopg.Connection = Depends(get_db)) -> StatsOut:
        total, by_status = stats_by_status(conn)
        return StatsOut(total=total, by_status=by_status)

    return app


app = create_app()
