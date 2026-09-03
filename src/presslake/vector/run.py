"""Boucle silver → chunks → embeddings → Qdrant."""

import psycopg
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from presslake.catalog.articles import STATUS_INDEXED, list_articles_to_embed, mark_embedded
from presslake.chunk.envelope import silver_to_chunks
from presslake.output import info, report_progress
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_json_object, get_s3_client, parse_s3_uri
from presslake.vector.client import get_qdrant_client
from presslake.vector.collection import COLLECTION_CHUNKS, recreate_collection, upsert_chunks
from presslake.vector.embed import embed_passages


def embed_article(
    conn: psycopg.Connection,
    s3_client: BaseClient,
    article: dict,
    *,
    qdrant_client=None,
) -> int:
    """
    Chunk + embed + upsert un article indexé.

    Returns:
        Nombre de chunks écrits.
    """
    silver_uri = article.get("silver_s3_uri")
    if not silver_uri:
        raise ValueError(f"article sans silver_s3_uri : {article.get('url', '?')}")

    bucket, key = parse_s3_uri(silver_uri)
    silver = get_json_object(s3_client, bucket, key)
    chunks = silver_to_chunks(silver, silver_s3_uri=silver_uri)
    if not chunks:
        raise ValueError(f"silver sans texte chunkable : {silver_uri}")

    vectors = embed_passages([chunk["text"] for chunk in chunks])
    client = qdrant_client or get_qdrant_client()
    written = upsert_chunks(client, chunks, vectors)

    mark_embedded(conn, article["url"])
    conn.commit()

    title = article.get("title") or "(sans titre)"
    info(
        f"[EMBEDDED] {article['feed_id']} | {title[:60]} | "
        f"{written} chunk(s)"
    )
    return written


def embed_all(*, limit: int | None = None, recreate: bool = False) -> int:
    """
    Embede les articles catalogue en status=indexed (ou re-embed si --recreate).

    Returns:
        Nombre total de chunks écrits.
    """
    s3_client = get_s3_client()
    chunk_count = 0
    article_count = 0
    errors = 0
    qdrant_client = get_qdrant_client()

    if recreate:
        recreate_collection(qdrant_client)
        info(f"Collection {COLLECTION_CHUNKS} recréée.")

    with get_connection() as conn:
        articles = list_articles_to_embed(
            conn,
            include_embedded=recreate,
            limit=limit,
        )

        article_total = len(articles)
        for index, article in enumerate(articles, start=1):
            try:
                written = embed_article(
                    conn,
                    s3_client,
                    article,
                    qdrant_client=qdrant_client,
                )
                chunk_count += written
                article_count += 1
            except (ValueError, OSError, ClientError, KeyError) as exc:
                errors += 1
                print(f"[SKIP] {article.get('url', '?')} — {exc}")
            report_progress(index, article_total)

    info(
        f"\n→ {article_count} article(s) embedé(s), {chunk_count} chunk(s)",
        end="",
    )
    if errors:
        info(f", {errors} ignoré(s)")
    else:
        info()

    return chunk_count
