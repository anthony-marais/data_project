"""Configuration RAG / Ollama."""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"
DEFAULT_RAG_TOP_K = 4
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"
DEFAULT_OLLAMA_NUM_PREDICT = 512


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL).rstrip("/")


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()


def rag_top_k() -> int:
    raw = os.environ.get("RAG_TOP_K", str(DEFAULT_RAG_TOP_K))
    return max(1, min(20, int(raw)))


def rag_min_vector_score() -> float:
    """
    Seuil cosine Qdrant : en dessous, un voisin n'est pas un vrai hit.

    Qdrant renvoie toujours top-k ; sans seuil le chat ne refuse jamais.
    0 désactive le filtre.
    """
    raw = os.environ.get("RAG_MIN_VECTOR_SCORE", "0.45")
    return max(0.0, min(1.0, float(raw)))


def ollama_keep_alive() -> str:
    """Durée de maintien du modèle en RAM côté Ollama (ex. 30m)."""
    return os.environ.get("OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE).strip()


def ollama_num_predict() -> int:
    """Limite de tokens générés — réduit la latence sur CPU."""
    raw = os.environ.get("OLLAMA_NUM_PREDICT", str(DEFAULT_OLLAMA_NUM_PREDICT))
    return max(64, min(4096, int(raw)))


def rag_warmup_enabled() -> bool:
    raw = os.environ.get("PRESSLAKE_RAG_WARMUP", "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def openai_compat_model_name() -> str:
    """Nom exposé aux clients Open WebUI / LibreChat."""
    return os.environ.get("PRESSLAKE_RAG_MODEL", "presslake-rag")
