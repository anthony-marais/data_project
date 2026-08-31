"""Enrichissement des chunks avec metadata silver (citations RAG)."""

from typing import Any

from presslake.chunk.split import chunk_text


def chunk_id(content_hash: str, chunk_index: int) -> str:
    """Identifiant stable d'un chunk dans Qdrant."""
    return f"{content_hash}:{chunk_index}"


def silver_to_chunks(silver: dict[str, Any], *, silver_s3_uri: str) -> list[dict[str, Any]]:
    """
    Produit les chunks citables d'un enveloppe silver v1.

    Chaque chunk porte assez de metadata pour une citation module 12 :
    content_hash, offsets, silver_s3_uri, langue, titre.
    """
    body = silver.get("text") or ""
    content_hash = silver["content_hash"]
    content_lang = silver.get("content_lang") or silver.get("feed_lang") or "und"

    return [
        {
            "chunk_id": chunk_id(content_hash, piece["chunk_index"]),
            "content_hash": content_hash,
            "chunk_index": piece["chunk_index"],
            "text": piece["text"],
            "char_start": piece["char_start"],
            "char_end": piece["char_end"],
            "feed_id": silver["feed_id"],
            "title": silver.get("title"),
            "content_lang": content_lang,
            "feed_lang": silver.get("feed_lang"),
            "silver_s3_uri": silver_s3_uri,
            "canonical_url": silver.get("canonical_url"),
        }
        for piece in chunk_text(body)
    ]
