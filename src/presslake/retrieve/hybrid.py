"""Fusion retrieve hybride OpenSearch (BM25) + Qdrant (vecteurs)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from presslake.retrieve.types import RetrievedPassage
from presslake.search.client import get_opensearch_client
from presslake.search.index import search_articles
from presslake.vector.client import get_qdrant_client
from presslake.vector.collection import search_similar
from presslake.vector.embed import embed_query

# Constante RRF classique (Cormack et al.) — robuste quand les échelles de score diffèrent.
RRF_K = 60

# Mots vides FR/EN + méta-eval : sans ça BM25 « match » n'importe quel article.
_LEXICAL_STOP = frozenset(
    """
    a an and are as at be by for from in is it of on or that the this to was were
    au aux avec ce ces dans de des du elle en et eux il je la le les leur lui ma
    mais me mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se
    ses son sur ta te tes toi ton tu un une vos votre vous y
    quel quelle quels quels quelles comment combien
    dit parle selon donne corpus presslake flux rss aujourd hui aujourd'hui
    article articles question réponse
    """.split()
)
_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ÿ_-]+", re.UNICODE)


def lexical_query(question: str) -> str | None:
    """
    Termes BM25 utiles : stopwords enlevés ; si un token « rare » (long / chiffre)
    est présent, on ne cherche que ceux-là (cas eval hors corpus).
    """
    tokens = [t for t in _TOKEN_RE.findall(question) if len(t) > 2]
    kept = [t for t in tokens if t.casefold() not in _LEXICAL_STOP]
    if not kept:
        return None
    rare = [t for t in kept if len(t) >= 12 or any(c.isdigit() for c in t)]
    chosen = rare if rare else kept
    return " ".join(chosen)


def _passage_from_bm25(hit: dict[str, Any]) -> RetrievedPassage:
    snippet = hit.get("snippet") or ""
    return RetrievedPassage(
        text=snippet,
        score=0.0,
        sources=("bm25",),
        content_hash=hit.get("content_hash"),
        chunk_index=None,
        feed_id=hit.get("feed_id"),
        title=hit.get("title"),
        content_lang=hit.get("content_lang"),
        canonical_url=hit.get("canonical_url"),
        silver_s3_uri=hit.get("silver_s3_uri"),
        lexical_score=float(hit.get("score") or 0),
    )


def _passage_from_vector(hit: dict[str, Any]) -> RetrievedPassage:
    chunk_index = hit.get("chunk_index")
    return RetrievedPassage(
        text=hit.get("text") or "",
        score=0.0,
        sources=("vector",),
        content_hash=hit.get("content_hash"),
        chunk_index=int(chunk_index) if chunk_index is not None else None,
        feed_id=hit.get("feed_id"),
        title=hit.get("title"),
        content_lang=hit.get("content_lang"),
        canonical_url=hit.get("canonical_url"),
        silver_s3_uri=hit.get("silver_s3_uri"),
        vector_score=float(hit.get("score") or 0),
    )


def _merge_passages(existing: RetrievedPassage, incoming: RetrievedPassage) -> RetrievedPassage:
    """Fusionne deux passages même clé (présents dans BM25 et vecteur)."""
    sources = tuple(dict.fromkeys((*existing.sources, *incoming.sources)))
    text = existing.text if len(existing.text) >= len(incoming.text) else incoming.text
    return RetrievedPassage(
        text=text,
        score=existing.score,
        sources=sources,
        content_hash=existing.content_hash or incoming.content_hash,
        chunk_index=(
            incoming.chunk_index
            if incoming.chunk_index is not None
            else existing.chunk_index
        ),
        feed_id=existing.feed_id or incoming.feed_id,
        title=existing.title or incoming.title,
        content_lang=existing.content_lang or incoming.content_lang,
        canonical_url=existing.canonical_url or incoming.canonical_url,
        silver_s3_uri=existing.silver_s3_uri or incoming.silver_s3_uri,
        lexical_score=existing.lexical_score or incoming.lexical_score,
        vector_score=existing.vector_score or incoming.vector_score,
    )


def fuse_rrf(
    ranked_lists: list[list[RetrievedPassage]],
    *,
    limit: int,
    k: int = RRF_K,
) -> list[RetrievedPassage]:
    """
    Reciprocal Rank Fusion — combine plusieurs classements sans normaliser les scores bruts.
    """
    scores: dict[str, float] = {}
    passages: dict[str, RetrievedPassage] = {}

    for ranked in ranked_lists:
        for rank, passage in enumerate(ranked, start=1):
            key = passage.dedup_key()
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key in passages:
                passages[key] = _merge_passages(passages[key], passage)
            else:
                passages[key] = passage

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    result: list[RetrievedPassage] = []
    for key, rrf_score in ordered[:limit]:
        base = passages[key]
        result.append(
            RetrievedPassage(
                text=base.text,
                score=rrf_score,
                sources=base.sources,
                content_hash=base.content_hash,
                chunk_index=base.chunk_index,
                feed_id=base.feed_id,
                title=base.title,
                content_lang=base.content_lang,
                canonical_url=base.canonical_url,
                silver_s3_uri=base.silver_s3_uri,
                lexical_score=base.lexical_score,
                vector_score=base.vector_score,
            )
        )
    return result


def _bm25_ranked(
    query: str,
    *,
    depth: int,
    lang: str | None,
) -> list[RetrievedPassage]:
    lexical = lexical_query(query)
    if not lexical:
        return []
    hits = search_articles(
        get_opensearch_client(),
        lexical,
        limit=depth,
        lang=lang,
    )
    return [_passage_from_bm25(hit) for hit in hits]


def _vector_ranked(
    query: str,
    *,
    depth: int,
    lang: str | None,
) -> list[RetrievedPassage]:
    hits = search_similar(
        get_qdrant_client(),
        embed_query(query),
        limit=depth,
        lang=lang,
    )
    return [_passage_from_vector(hit) for hit in hits]


def filter_relevant_passages(
    passages: list[RetrievedPassage],
    *,
    min_vector_score: float | None = None,
) -> list[RetrievedPassage]:
    """
    Écarte les voisins Qdrant trop faibles (hors sujet).

    Un hit BM25 est conservé. Un passage vector-only doit dépasser
    `RAG_MIN_VECTOR_SCORE` (défaut 0.45). Qdrant renvoie toujours un top-k.
    """
    if min_vector_score is None:
        from presslake.rag.config import rag_min_vector_score

        min_vector_score = rag_min_vector_score()
    if min_vector_score <= 0:
        return list(passages)

    kept: list[RetrievedPassage] = []
    for passage in passages:
        if "bm25" in passage.sources:
            kept.append(passage)
            continue
        if passage.vector_score is not None and passage.vector_score >= min_vector_score:
            kept.append(passage)
    return kept


def retrieve_passages(
    query: str,
    *,
    limit: int = 10,
    lang: str | None = None,
    per_source_limit: int | None = None,
    bm25_only: bool = False,
    vector_only: bool = False,
    skip_min_score: bool = False,
) -> list[RetrievedPassage]:
    """
    Retrieve hybride one-shot : BM25 + similarité sémantique, fusion RRF.

    Args:
        query: question ou mots-clés utilisateur.
        limit: nombre max de passages retournés après fusion.
        lang: filtre optionnel `fr` ou `en` (OpenSearch + Qdrant).
        per_source_limit: profondeur par moteur (défaut = limit).
        bm25_only / vector_only: forcer un seul moteur (debug).
        skip_min_score: ne pas filtrer les voisins Qdrant trop faibles.

    Returns:
        Passages triés par score RRF décroissant, après seuil vectoriel.
    """
    if bm25_only and vector_only:
        raise ValueError("bm25_only et vector_only sont mutuellement exclusifs")

    depth = per_source_limit if per_source_limit is not None else max(limit, 10)
    ranked: list[list[RetrievedPassage]] = []

    run_bm25 = not vector_only
    run_vector = not bm25_only

    if run_bm25 and run_vector:
        with ThreadPoolExecutor(max_workers=2) as pool:
            bm25_future = pool.submit(_bm25_ranked, query, depth=depth, lang=lang)
            vector_future = pool.submit(_vector_ranked, query, depth=depth, lang=lang)
            bm25_passages = bm25_future.result()
            vector_passages = vector_future.result()
        if bm25_passages:
            ranked.append(bm25_passages)
        if vector_passages:
            ranked.append(vector_passages)
    elif run_bm25:
        ranked.append(_bm25_ranked(query, depth=depth, lang=lang))
    elif run_vector:
        ranked.append(_vector_ranked(query, depth=depth, lang=lang))

    if not ranked:
        return []

    if len(ranked) == 1:
        fused = [
            RetrievedPassage(
                text=p.text,
                score=p.lexical_score or p.vector_score or 0.0,
                sources=p.sources,
                content_hash=p.content_hash,
                chunk_index=p.chunk_index,
                feed_id=p.feed_id,
                title=p.title,
                content_lang=p.content_lang,
                canonical_url=p.canonical_url,
                silver_s3_uri=p.silver_s3_uri,
                lexical_score=p.lexical_score,
                vector_score=p.vector_score,
            )
            for p in ranked[0][:limit]
        ]
    else:
        fused = fuse_rrf(ranked, limit=limit)

    if skip_min_score:
        return fused
    return filter_relevant_passages(fused)
