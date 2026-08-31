"""Collection Qdrant presslake-chunks."""

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from presslake.vector.config import COLLECTION_CHUNKS, VECTOR_SIZE


def chunk_point_uuid(chunk_id: str) -> str:
    """UUID déterministe à partir du chunk_id (idempotent)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def ensure_collection(client: QdrantClient, *, vector_size: int = VECTOR_SIZE) -> None:
    """Crée la collection si absente."""
    if client.collection_exists(COLLECTION_CHUNKS):
        return
    client.create_collection(
        collection_name=COLLECTION_CHUNKS,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def recreate_collection(client: QdrantClient, *, vector_size: int = VECTOR_SIZE) -> None:
    """Supprime et recrée la collection (changement de modèle / mapping)."""
    if client.collection_exists(COLLECTION_CHUNKS):
        client.delete_collection(COLLECTION_CHUNKS)
    ensure_collection(client, vector_size=vector_size)


def upsert_chunks(
    client: QdrantClient,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
) -> int:
    """
    Indexe ou remplace des chunks (id = chunk_id).

    Returns:
        Nombre de points écrits.
    """
    if not chunks:
        return 0
    if len(chunks) != len(vectors):
        raise ValueError("chunks et vectors doivent avoir la même longueur")

    ensure_collection(client)
    points = [
        PointStruct(
            id=chunk_point_uuid(chunk["chunk_id"]),
            vector=vector,
            payload={
                "chunk_id": chunk["chunk_id"],
                "content_hash": chunk["content_hash"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"],
                "feed_id": chunk["feed_id"],
                "title": chunk.get("title"),
                "content_lang": chunk.get("content_lang"),
                "feed_lang": chunk.get("feed_lang"),
                "silver_s3_uri": chunk["silver_s3_uri"],
                "canonical_url": chunk.get("canonical_url"),
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=COLLECTION_CHUNKS, points=points)
    return len(points)


def search_similar(
    client: QdrantClient,
    query_vector: list[float],
    *,
    limit: int = 5,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """
    Recherche par similarité cosinus.

    Returns:
        Hits {score, chunk_id, title, text, silver_s3_uri, …}.
    """
    if not client.collection_exists(COLLECTION_CHUNKS):
        return []

    query_filter = None
    if lang:
        query_filter = Filter(
            must=[FieldCondition(key="content_lang", match=MatchValue(value=lang))]
        )

    response = client.query_points(
        collection_name=COLLECTION_CHUNKS,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )

    hits: list[dict[str, Any]] = []
    for point in response.points:
        payload = point.payload or {}
        hits.append(
            {
                "score": point.score,
                "chunk_id": payload.get("chunk_id"),
                "content_hash": payload.get("content_hash"),
                "chunk_index": payload.get("chunk_index"),
                "feed_id": payload.get("feed_id"),
                "title": payload.get("title"),
                "content_lang": payload.get("content_lang"),
                "text": payload.get("text"),
                "silver_s3_uri": payload.get("silver_s3_uri"),
                "canonical_url": payload.get("canonical_url"),
            }
        )
    return hits


def count_points(client: QdrantClient) -> int:
    """Nombre de points dans la collection (0 si absente)."""
    if not client.collection_exists(COLLECTION_CHUNKS):
        return 0
    return int(client.count(collection_name=COLLECTION_CHUNKS, exact=True).count)
