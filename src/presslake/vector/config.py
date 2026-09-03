"""Configuration Qdrant + modèle d'embedding."""

import os

from dotenv import load_dotenv

load_dotenv()

COLLECTION_CHUNKS = "presslake-chunks"
# Multilingue (ADR 0003) — 384 dimensions, supporté par fastembed.
DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
VECTOR_SIZE = 384


def _embed_params() -> dict:
    try:
        from presslake.mlops.params import load_embed_params

        return load_embed_params()
    except (OSError, ValueError):
        return {}


def embedding_model() -> str:
    """Modèle fastembed — changer nécessite un `presslake embed --recreate`."""
    env = os.environ.get("EMBEDDING_MODEL")
    if env is not None and env.strip():
        return env.strip()
    from_params = _embed_params().get("model")
    if isinstance(from_params, str) and from_params.strip():
        return from_params.strip()
    return DEFAULT_EMBEDDING_MODEL


def embedding_vector_size() -> int:
    """Taille du vecteur (doit matcher le modèle). Recreate Qdrant si ça change."""
    env = os.environ.get("EMBEDDING_VECTOR_SIZE")
    if env is not None and env.strip():
        return int(env.strip())
    from_params = _embed_params().get("vector_size")
    if from_params is not None:
        return int(from_params)
    return VECTOR_SIZE


def qdrant_url() -> str:
    raw = os.environ.get("QDRANT_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "QDRANT_URL non configuré — définir dans .env ou lancer Qdrant (compose)."
        )
    return raw.rstrip("/")
