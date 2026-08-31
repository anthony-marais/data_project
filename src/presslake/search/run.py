"""Boucle d'indexation silver → OpenSearch."""

import psycopg
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from presslake.catalog.articles import list_articles_to_index, mark_indexed
from presslake.search.client import get_opensearch_client
from presslake.search.config import INDEX_ARTICLES
from presslake.search.index import ensure_index, index_document, recreate_index, silver_to_document
from presslake.storage.postgres import get_connection
from presslake.storage.s3 import get_json_object, get_s3_client, parse_s3_uri


def index_article(
    conn: psycopg.Connection,
    s3_client: BaseClient,
    article: dict,
    *,
    os_client=None,
) -> None:
    """
    Indexe un article parsé : lit silver MinIO → OpenSearch → status=indexed.

    Idempotent : même content_hash remplace le document OpenSearch.
    """
    silver_uri = article.get("silver_s3_uri")
    if not silver_uri:
        raise ValueError(f"article sans silver_s3_uri : {article.get('url', '?')}")

    bucket, key = parse_s3_uri(silver_uri)
    silver = get_json_object(s3_client, bucket, key)
    doc = silver_to_document(silver, silver_s3_uri=silver_uri)

    client = os_client or get_opensearch_client()
    ensure_index(client)
    index_document(client, doc)
    mark_indexed(conn, article["url"])
    conn.commit()

    title = doc.get("title") or "(sans titre)"
    lang = doc.get("content_lang", "?")
    print(f"[INDEXED] {doc['feed_id']} | {title[:60]} | lang={lang}")


def index_all(*, limit: int | None = None, recreate: bool = False) -> int:
    """
    Indexe les articles catalogue en status=parsed (ou re-index si --recreate).

    Returns:
        Nombre d'articles indexés avec succès.
    """
    s3_client = get_s3_client()
    indexed_count = 0
    errors = 0
    os_client = get_opensearch_client()

    if recreate:
        recreate_index(os_client)
        print(f"Index {INDEX_ARTICLES} recréé.")

    with get_connection() as conn:
        articles = list_articles_to_index(
            conn,
            include_indexed=recreate,
            limit=limit,
        )

        for article in articles:
            try:
                index_article(conn, s3_client, article, os_client=os_client)
                indexed_count += 1
            except (ValueError, OSError, ClientError, KeyError) as exc:
                errors += 1
                print(f"[SKIP] {article.get('url', '?')} — {exc}")

    print(f"\n→ {indexed_count} article(s) indexé(s)", end="")
    if errors:
        print(f", {errors} ignoré(s)")
    else:
        print()

    return indexed_count
