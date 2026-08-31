"""
Application FastAPI — catalogue PressLake (lecture seule).

Lancer : uv run presslake serve
Docs   : http://localhost:8000/docs
Métriques : http://localhost:8000/metrics
"""

import asyncio
import logging
from contextlib import asynccontextmanager

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
from presslake.api.openai_compat import router as openai_router
from presslake.api.schemas import (
    ArticleListOut,
    ArticleOut,
    ChatRequest,
    ChatResponse,
    HealthOut,
    OpsStatusOut,
    RetrieveOut,
    RetrievedPassageOut,
    StatsOut,
)
from presslake.observability.alerts import evaluate_ops_status
from presslake.observability.catalog_metrics import refresh_metrics_from_postgres
from presslake.retrieve.hybrid import retrieve_passages
from presslake.rag.chat import answer_question
from presslake.rag.ollama import OllamaError
from presslake.rag.warmup import warmup_rag_stack

MAX_PAGE_SIZE = 200
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _rag_lifespan(_app: FastAPI):
    """Précharge embed + Ollama au démarrage (hors event loop)."""
    try:
        await asyncio.to_thread(warmup_rag_stack)
    except Exception:
        logger.exception("Échec du warmup RAG au démarrage")
    yield


def create_app() -> FastAPI:
    """Fabrique l'app (utile pour tests et uvicorn)."""
    app = FastAPI(
        title="PressLake API",
        description=(
            "Catalogue Postgres, retrieve hybride RAG, chat Ollama local. "
            "Compatible Open WebUI / LibreChat via /v1/chat/completions."
        ),
        version="0.1.0",
        lifespan=_rag_lifespan,
    )

    app.include_router(openai_router)

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

    @app.get("/retrieve", response_model=RetrieveOut, tags=["rag"])
    def get_retrieve(
        q: str = Query(..., min_length=1, description="Question ou mots-clés"),
        limit: int = Query(default=10, ge=1, le=50),
        lang: str | None = Query(default=None, pattern="^(fr|en)$"),
    ) -> RetrieveOut:
        """
        Retrieve hybride one-shot (BM25 + Qdrant, fusion RRF).

        Interface réutilisable par le chat (module 12), MCP (14) et toute UI externe.
        Pas d'appel LLM — uniquement des passages citables.
        """
        passages = retrieve_passages(q, limit=limit, lang=lang)
        return RetrieveOut(
            query=q,
            limit=limit,
            passages=[
                RetrievedPassageOut(
                    text=p.text,
                    score=p.score,
                    sources=list(p.sources),
                    content_hash=p.content_hash,
                    chunk_index=p.chunk_index,
                    feed_id=p.feed_id,
                    title=p.title,
                    content_lang=p.content_lang,
                    canonical_url=p.canonical_url,
                    silver_s3_uri=p.silver_s3_uri,
                )
                for p in passages
            ],
        )

    @app.post("/chat", response_model=ChatResponse, tags=["rag"])
    def post_chat(body: ChatRequest) -> ChatResponse:
        """
        Chat RAG JSON simple (retrieve + Ollama local).

        Pour Open WebUI / LibreChat, préférer POST /v1/chat/completions.
        """
        try:
            result = answer_question(body.message, limit=body.limit, lang=body.lang)
        except OllamaError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return ChatResponse(
            message=body.message,
            answer=result.answer,
            refused=result.refused,
            model=result.model,
            passages=[
                RetrievedPassageOut(
                    text=p.text,
                    score=p.score,
                    sources=list(p.sources),
                    content_hash=p.content_hash,
                    chunk_index=p.chunk_index,
                    feed_id=p.feed_id,
                    title=p.title,
                    content_lang=p.content_lang,
                    canonical_url=p.canonical_url,
                    silver_s3_uri=p.silver_s3_uri,
                )
                for p in result.passages
            ],
        )

    return app


app = create_app()
