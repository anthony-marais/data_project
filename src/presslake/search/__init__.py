"""Recherche lexicale OpenSearch (module 10)."""

from presslake.search.client import get_opensearch_client
from presslake.search.index import count_documents, search_articles

__all__ = ["count_documents", "get_opensearch_client", "search_articles"]
