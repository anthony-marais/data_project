"""Index OpenSearch presslake-articles (mapping BM25 + langues)."""

from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError

from presslake.search.config import INDEX_ARTICLES

INDEX_BODY: dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "feed_id": {"type": "keyword"},
            "content_hash": {"type": "keyword"},
            "feed_lang": {"type": "keyword"},
            "content_lang": {"type": "keyword"},
            "title": {"type": "text"},
            "text": {"type": "text"},
            "title_fr": {"type": "text", "analyzer": "french"},
            "text_fr": {"type": "text", "analyzer": "french"},
            "title_en": {"type": "text", "analyzer": "english"},
            "text_en": {"type": "text", "analyzer": "english"},
            "canonical_url": {"type": "keyword"},
            "bronze_s3_uri": {"type": "keyword"},
            "silver_s3_uri": {"type": "keyword"},
            "author": {"type": "text"},
            "published_at": {"type": "date", "ignore_malformed": True},
            "parsed_at": {"type": "date", "ignore_malformed": True},
        }
    },
}


def ensure_index(client: OpenSearch) -> None:
    """Crée l'index presslake-articles s'il n'existe pas."""
    if client.indices.exists(index=INDEX_ARTICLES):
        return
    client.indices.create(index=INDEX_ARTICLES, body=INDEX_BODY)


def recreate_index(client: OpenSearch) -> None:
    """Supprime et recrée l'index (après changement de mapping)."""
    if client.indices.exists(index=INDEX_ARTICLES):
        client.indices.delete(index=INDEX_ARTICLES)
    client.indices.create(index=INDEX_ARTICLES, body=INDEX_BODY)


def _resolve_langs(silver: dict[str, Any]) -> tuple[str, str]:
    feed_lang = silver.get("feed_lang") or "und"
    content_lang = silver.get("content_lang") or feed_lang or "und"
    return feed_lang, content_lang


def silver_to_document(silver: dict[str, Any], *, silver_s3_uri: str) -> dict[str, Any]:
    """Mappe un enveloppe silver v1 vers un document OpenSearch."""
    feed_lang, content_lang = _resolve_langs(silver)
    title = silver.get("title") or ""
    text = silver["text"]

    doc: dict[str, Any] = {
        "feed_id": silver["feed_id"],
        "content_hash": silver["content_hash"],
        "feed_lang": feed_lang,
        "content_lang": content_lang,
        "title": title,
        "text": text,
        "title_fr": title if content_lang == "fr" else "",
        "text_fr": text if content_lang == "fr" else "",
        "title_en": title if content_lang == "en" else "",
        "text_en": text if content_lang == "en" else "",
        "canonical_url": silver.get("canonical_url") or "",
        "bronze_s3_uri": silver["bronze_s3_uri"],
        "silver_s3_uri": silver_s3_uri,
        "author": silver.get("author") or "",
        "parsed_at": silver.get("parsed_at"),
    }
    published = silver.get("published")
    if published:
        doc["published_at"] = published
    return doc


def index_document(client: OpenSearch, doc: dict[str, Any]) -> None:
    """Indexe ou remplace un article (id = content_hash)."""
    client.index(
        index=INDEX_ARTICLES,
        id=doc["content_hash"],
        body=doc,
        refresh=True,
    )


def search_articles(
    client: OpenSearch,
    query: str,
    *,
    limit: int = 10,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """
    Recherche BM25 multi-champs (titre boosté).

    Args:
        lang: filtre optionnel `fr` ou `en` (champs analyzés dédiés).

    Returns:
        Liste de hits {_score, feed_id, title, canonical_url, snippet, …}.
    """
    if not client.indices.exists(index=INDEX_ARTICLES):
        return []

    if lang in ("fr", "en"):
        fields = [f"title_{lang}^2", f"text_{lang}"]
        query_clause: dict[str, Any] = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": fields,
                            "type": "best_fields",
                        }
                    }
                ],
                "filter": [{"term": {"content_lang": lang}}],
            }
        }
        highlight_fields = {f"text_{lang}": {}, f"title_{lang}": {}}
    else:
        query_clause = {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "text"],
                "type": "best_fields",
            }
        }
        highlight_fields = {"text": {}, "title": {}}

    response = client.search(
        index=INDEX_ARTICLES,
        body={
            "size": limit,
            "query": query_clause,
            "highlight": {
                "fields": highlight_fields,
                "fragment_size": 120,
            },
        },
    )

    hits: list[dict[str, Any]] = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        highlight = hit.get("highlight", {})
        snippet = None
        for key in highlight:
            if highlight[key]:
                snippet = highlight[key][0]
                break
        if snippet is None:
            snippet = (source.get("text") or "")[:120]
        hits.append(
            {
                "score": hit["_score"],
                "content_hash": source.get("content_hash"),
                "feed_id": source.get("feed_id"),
                "title": source.get("title"),
                "content_lang": source.get("content_lang"),
                "canonical_url": source.get("canonical_url"),
                "silver_s3_uri": source.get("silver_s3_uri"),
                "snippet": snippet,
            }
        )
    return hits


def count_documents(client: OpenSearch) -> int:
    """Nombre de documents dans l'index (0 si absent)."""
    try:
        return int(client.count(index=INDEX_ARTICLES)["count"])
    except NotFoundError:
        return 0
