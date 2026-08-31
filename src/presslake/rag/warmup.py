"""Préchargement embed + Ollama au démarrage de l'API."""

import logging

from presslake.rag.config import ollama_model, rag_warmup_enabled
from presslake.rag.ollama import OllamaError, warmup_ollama
from presslake.vector.embed import embed_query

logger = logging.getLogger(__name__)


def warmup_rag_stack() -> None:
    """
    Charge le modèle fastembed et préchauffe Ollama (évite ~10 s au 1er message).

    Désactiver : PRESSLAKE_RAG_WARMUP=false
    """
    if not rag_warmup_enabled():
        logger.info("RAG warmup désactivé (PRESSLAKE_RAG_WARMUP=false).")
        return

    logger.info("RAG warmup : chargement modèle embedding…")
    embed_query("presslake warmup")

    logger.info("RAG warmup : préchargement Ollama (%s)…", ollama_model())
    try:
        warmup_ollama()
        logger.info("RAG warmup terminé.")
    except OllamaError as exc:
        logger.warning("RAG warmup Ollama ignoré — %s", exc)
