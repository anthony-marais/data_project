"""Outils MCP PressLake : search (retrieve) + read (silver seulement)."""

from __future__ import annotations

import json
from typing import Any

from presslake.catalog.articles import get_article_by_content_hash
from presslake.retrieve.hybrid import retrieve_passages
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_json_object, get_s3_client, parse_s3_uri

DEFAULT_SEARCH_LIMIT = 5
DEFAULT_READ_CHARS = 4000
MAX_READ_CHARS = 12000


def search_corpus(query: str, *, limit: int = DEFAULT_SEARCH_LIMIT, lang: str | None = None) -> str:
    """
    Retrieve hybride (même moteur que `presslake retrieve` / le chat).

    Returns:
        JSON : liste de passages citables (pas de génération LLM).
    """
    q = query.strip()
    if not q:
        return json.dumps({"error": "query vide"}, ensure_ascii=False)
    cap = max(1, min(int(limit), 20))
    passages = retrieve_passages(q, limit=cap, lang=lang)
    payload = {
        "query": q,
        "count": len(passages),
        "passages": [
            {
                "title": p.title,
                "score": round(p.score, 4),
                "sources": list(p.sources),
                "content_hash": p.content_hash,
                "chunk_index": p.chunk_index,
                "feed_id": p.feed_id,
                "content_lang": p.content_lang,
                "canonical_url": p.canonical_url,
                "silver_s3_uri": p.silver_s3_uri,
                "text": (p.text or "")[:800],
            }
            for p in passages
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _assert_silver_uri(s3_uri: str) -> tuple[str, str]:
    bucket, key = parse_s3_uri(s3_uri)
    if not key.startswith("silver/"):
        raise ValueError(
            "read refuse le bronze et tout chemin hors silver/ — "
            f"uri={s3_uri!r}"
        )
    return bucket, key


def read_silver(
    *,
    content_hash: str | None = None,
    silver_s3_uri: str | None = None,
    max_chars: int = DEFAULT_READ_CHARS,
) -> str:
    """
    Lit un objet **silver** MinIO (texte + metadata). Jamais le HTML bronze.

    Identifier : `content_hash` (catalogue) **ou** `silver_s3_uri`.
    """
    cap = max(200, min(int(max_chars), MAX_READ_CHARS))
    uri = (silver_s3_uri or "").strip() or None
    digest = (content_hash or "").strip() or None

    if uri and digest:
        return json.dumps(
            {"error": "fournir content_hash OU silver_s3_uri, pas les deux"},
            ensure_ascii=False,
        )
    if not uri and not digest:
        return json.dumps(
            {"error": "il faut content_hash ou silver_s3_uri (après search)"},
            ensure_ascii=False,
        )

    meta: dict[str, Any] = {}
    if digest:
        with get_connection() as conn:
            row = get_article_by_content_hash(conn, digest)
        if row is None:
            return json.dumps(
                {"error": f"content_hash inconnu du catalogue : {digest}"},
                ensure_ascii=False,
            )
        uri = row.get("silver_s3_uri")
        if not uri:
            return json.dumps(
                {
                    "error": "article pas encore parsé (pas de silver)",
                    "content_hash": digest,
                    "status": row.get("status"),
                },
                ensure_ascii=False,
            )
        meta = {
            "title": row.get("title"),
            "url": row.get("url"),
            "feed_id": row.get("feed_id"),
            "status": row.get("status"),
        }

    assert uri is not None
    try:
        bucket, key = _assert_silver_uri(uri)
        silver = get_json_object(get_s3_client(), bucket, key)
    except (ValueError, OSError, KeyError) as exc:
        return json.dumps({"error": str(exc), "silver_s3_uri": uri}, ensure_ascii=False)

    text = str(silver.get("text") or "")
    truncated = len(text) > cap
    body = text[:cap]
    out = {
        "silver_s3_uri": uri,
        "content_hash": silver.get("content_hash") or digest,
        "title": silver.get("title") or meta.get("title"),
        "feed_id": silver.get("feed_id") or meta.get("feed_id"),
        "canonical_url": silver.get("canonical_url") or meta.get("url"),
        "text_source": silver.get("text_source"),
        "content_lang": silver.get("content_lang"),
        "truncated": truncated,
        "text": body,
    }
    return json.dumps(out, ensure_ascii=False)
