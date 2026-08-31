"""Types normalisés pour le retrieve RAG."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievedPassage:
    """
    Passage citables — unité commune BM25 (article) et Qdrant (chunk).

    Utilisé par le CLI `retrieve`, l'API `/retrieve` et le futur chat RAG.
    """

    text: str
    score: float
    sources: tuple[str, ...]
    content_hash: str | None = None
    chunk_index: int | None = None
    feed_id: str | None = None
    title: str | None = None
    content_lang: str | None = None
    canonical_url: str | None = None
    silver_s3_uri: str | None = None
    lexical_score: float | None = field(default=None, repr=False)
    vector_score: float | None = field(default=None, repr=False)

    def dedup_key(self) -> str:
        """Clé stable pour fusionner BM25 et vecteurs."""
        if self.content_hash is not None and self.chunk_index is not None:
            return f"{self.content_hash}:{self.chunk_index}"
        if self.content_hash:
            return f"{self.content_hash}:article"
        if self.silver_s3_uri:
            return self.silver_s3_uri
        return self.text[:80]

    def citation_label(self) -> str:
        """Libellé court pour affichage / prompt LLM."""
        title = (self.title or "(sans titre)")[:60]
        if self.chunk_index is not None:
            return f"{title} [chunk {self.chunk_index}]"
        return title
