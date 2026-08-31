"""Client Qdrant."""

from functools import lru_cache
from urllib.parse import urlparse

from qdrant_client import QdrantClient

from presslake.vector.config import qdrant_url


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Client HTTP vers Qdrant local (dev, sans TLS)."""
    url = qdrant_url()
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6333
    return QdrantClient(host=host, port=port, prefer_grpc=False, check_compatibility=False)
