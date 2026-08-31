"""Client OpenSearch."""

from functools import lru_cache
from urllib.parse import urlparse

from opensearchpy import OpenSearch

from presslake.search.config import opensearch_url


@lru_cache(maxsize=1)
def get_opensearch_client() -> OpenSearch:
    """Fabrique un client HTTP vers OpenSearch local (sécurité désactivée en dev)."""
    url = opensearch_url()
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 9200)
    use_ssl = parsed.scheme == "https"

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=use_ssl,
        verify_certs=False,
        ssl_show_warn=False,
    )
