"""Configuration Qdrant + modèle d'embedding."""

import os

from dotenv import load_dotenv

load_dotenv()

COLLECTION_CHUNKS = "presslake-chunks"
# Multilingue (ADR 0003) — 384 dimensions, supporté par fastembed.
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384


def qdrant_url() -> str:
    raw = os.environ.get("QDRANT_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "QDRANT_URL non configuré — définir dans .env ou lancer Qdrant (compose)."
        )
    return raw.rstrip("/")
