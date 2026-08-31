"""Configuration OpenSearch (module 10)."""

import os

from dotenv import load_dotenv

load_dotenv()

INDEX_ARTICLES = "presslake-articles"


def opensearch_url() -> str:
    raw = os.environ.get("OPENSEARCH_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "OPENSEARCH_URL non configuré — définir dans .env ou lancer OpenSearch (compose)."
        )
    return raw.rstrip("/")
