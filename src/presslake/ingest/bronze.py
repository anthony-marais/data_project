"""
Écriture couche bronze dans MinIO.

Convention PressLake (médaillon) :
  s3://{bucket}/bronze/source={feed_id}/dt={YYYY-MM-DD}/{content_hash}.json

Le bronze est immuable : on ajoute des objets, on ne réécrit pas l'historique.
Même item_key → même content_hash → même clé S3 (idempotent).
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from botocore.client import BaseClient

from presslake.contracts.validate import validate_bronze
from presslake.ingest.feeds import Feed

RAW_ENTRY_FIELDS = (
    "title",
    "link",
    "id",
    "guid",
    "summary",
    "published",
    "updated",
    "author",
    "tags",
)


def item_key(entry: dict) -> str:
    """
    Clé stable d'un article RSS/Atom (id → guid → link).

    Partagée par poll (dédup) et bronze (content_hash).
    """
    for field in ("id", "guid", "link"):
        value = entry.get(field)
        if value:
            return str(value).strip()
    raise ValueError(f"item sans clé : title={entry.get('title')!r}")


def content_hash(item_key_value: str) -> str:
    """
    Empreinte SHA-256 hex du item_key.

    Sert de nom de fichier : stable, déterministe, même article = même hash.
    """
    return hashlib.sha256(item_key_value.encode("utf-8")).hexdigest()


def partition_date(entry: dict) -> str:
    """
    Date de partition dt=YYYY-MM-DD pour le chemin S3.

    Priorité :
      1. published_parsed (struct time feedparser, UTC)
      2. aujourd'hui UTC si date de publication absente
    """
    published = entry.get("published_parsed")
    if published:
        return datetime(*published[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def bronze_s3_key(feed: Feed, entry: dict) -> str:
    """
    Clé objet dans le bucket (sans préfixe s3://).

    Exemple :
      bronze/source=france24/dt=2026-08-31/a3f2…c1.json
    """
    key_hash = content_hash(item_key(entry))
    dt = partition_date(entry)
    return f"bronze/source={feed.id}/dt={dt}/{key_hash}.json"


def bronze_s3_uri(bucket: str, key: str) -> str:
    """URI logique stockée plus tard dans le catalogue Postgres (module 04)."""
    return f"s3://{bucket}/{key}"


def entry_to_raw(entry: dict) -> dict[str, Any]:
    """
    Sous-ensemble de l'entry feedparser sérialisable en JSON.

    On filtre les champs connus plutôt que de dumper tout l'objet feedparser
    (certains attributs internes ne passent pas json.dumps).
    """
    return {field: entry[field] for field in RAW_ENTRY_FIELDS if field in entry}


def build_bronze_envelope(feed: Feed, entry: dict) -> dict[str, Any]:
    """
    Enveloppe bronze v1 : métadonnées + raw.

    schema_version permet d'évoluer le format sans casser les rejeux.
    source=rss_item : plus tard rss_item + html_permalink, etc.
    """
    stable_key = item_key(entry)
    return {
        "schema_version": 1,
        "feed_id": feed.id,
        "item_key": stable_key,
        "content_hash": content_hash(stable_key),
        "title": entry.get("title"),
        "link": entry.get("link"),
        "published": entry.get("published"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "rss_item",
        "raw": entry_to_raw(entry),
    }


def put_bronze(
    client: BaseClient,
    bucket: str,
    key: str,
    envelope: dict[str, Any],
) -> str:
    """
    Écrit l'enveloppe JSON dans MinIO via put_object.

    Returns:
        s3_uri de l'objet écrit (affiché dans les logs poll).

    Note idempotence : un 2e put sur la même clé écrase avec le même chemin ;
    seen.json évite les re-traitements inutiles côté ingest.
    """
    validate_bronze(envelope)

    body = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return bronze_s3_uri(bucket, key)


def write_entry_bronze(
    client: BaseClient,
    bucket: str,
    feed: Feed,
    entry: dict,
) -> str:
    """
    Raccourci : enveloppe + clé + put pour un article.

    Appelé depuis poll_feed() quand mark_seen retourne False (item nouveau).
    """
    envelope = build_bronze_envelope(feed, entry)
    key = bronze_s3_key(feed, entry)
    return put_bronze(client, bucket, key, envelope)
