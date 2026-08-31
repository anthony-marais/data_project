"""Embeddings locaux via fastembed (ONNX, multilingue)."""

from functools import lru_cache

from fastembed import TextEmbedding

from presslake.vector.config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    """Charge le modèle une fois (téléchargement ONNX au premier appel)."""
    return TextEmbedding(model_name=EMBEDDING_MODEL)


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Vecteurs pour les chunks indexés."""
    if not texts:
        return []
    return [vector.tolist() for vector in get_embedding_model().embed(texts)]


def embed_query(query: str) -> list[float]:
    """Vecteur pour une requête utilisateur (même espace que les passages)."""
    return list(get_embedding_model().embed([query.strip()]))[0].tolist()
