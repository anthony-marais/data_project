"""
Écriture couche silver dans MinIO.

Convention :
  s3://{bucket}/silver/source={feed_id}/dt={YYYY-MM-DD}/{content_hash}.json
"""

import re
from datetime import datetime, timezone
from typing import Any

from botocore.client import BaseClient

from presslake.storage.s3 import put_json_object

# Reprend la partition dt= de la clé bronze (cohérence médaillon).
_DT_PATTERN = re.compile(r"dt=([^/]+)")


def dt_from_bronze_key(bronze_key: str) -> str:
    """
    Extrait dt=YYYY-MM-DD depuis la clé bronze.

    Ex. bronze/source=france24/dt=2026-08-31/abc.json → 2026-08-31
    """
    match = _DT_PATTERN.search(bronze_key)
    if match:
        return match.group(1)
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def silver_s3_key(feed_id: str, dt: str, content_hash: str) -> str:
    """Clé objet silver (sans préfixe s3://)."""
    return f"silver/source={feed_id}/dt={dt}/{content_hash}.json"


def build_silver_envelope(
    bronze: dict[str, Any],
    *,
    text: str,
    text_source: str,
    bronze_s3_uri: str,
) -> dict[str, Any]:
    """
    Enveloppe silver v1 — texte lisible + metadata.

    Champs alignés architecture : titre, texte, canonical_url, hash, source extraction.
    """
    raw = bronze.get("raw") or {}
    return {
        "schema_version": 1,
        "feed_id": bronze["feed_id"],
        "content_hash": bronze["content_hash"],
        "title": bronze.get("title"),
        "canonical_url": bronze.get("link"),
        "author": raw.get("author"),
        "published": bronze.get("published"),
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "text_source": text_source,
        "bronze_s3_uri": bronze_s3_uri,
    }


def write_silver_from_bronze(
    client: BaseClient,
    bucket: str,
    bronze: dict[str, Any],
    *,
    bronze_s3_uri: str,
    bronze_key: str,
    text: str,
    text_source: str,
) -> str:
    """
    Construit l'enveloppe silver et l'écrit dans MinIO.

    Returns:
        s3_uri silver.
    """
    envelope = build_silver_envelope(
        bronze,
        text=text,
        text_source=text_source,
        bronze_s3_uri=bronze_s3_uri,
    )
    dt = dt_from_bronze_key(bronze_key)
    key = silver_s3_key(bronze["feed_id"], dt, bronze["content_hash"])
    return put_json_object(client, bucket, key, envelope)
