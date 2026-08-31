"""Consommateur Kafka pour les événements ingest."""

import json
from collections.abc import Iterator
from typing import Any

from kafka import KafkaConsumer, TopicPartition

from presslake.events.config import CONSUMER_GROUP_PARSE, bootstrap_servers
from presslake.events.producer import EVENT_ARTICLE_INGESTED
from presslake.events.topics import TOPIC_ARTICLES_INGESTED


def _require_servers() -> list[str]:
    servers = bootstrap_servers()
    if not servers:
        raise RuntimeError(
            "KAFKA_BOOTSTRAP_SERVERS non configuré — définir dans .env ou lancer Redpanda."
        )
    return servers


def iter_article_ingested(
    *,
    replay: bool = False,
    limit: int | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Itère les événements article.ingested depuis le topic.

    Args:
        replay: si True, rejeu depuis l'offset 0 (sans consumer group).
        limit: nombre max de messages à lire.
    """
    servers = _require_servers()
    consumer = KafkaConsumer(
        bootstrap_servers=servers,
        group_id=None if replay else CONSUMER_GROUP_PARSE,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        enable_auto_commit=not replay,
        auto_offset_reset="earliest",
        consumer_timeout_ms=2_000,
    )

    try:
        if replay:
            partitions = consumer.partitions_for_topic(TOPIC_ARTICLES_INGESTED)
            if not partitions:
                return
            assignments = [
                TopicPartition(TOPIC_ARTICLES_INGESTED, partition)
                for partition in partitions
            ]
            consumer.assign(assignments)
            consumer.seek_to_beginning(*assignments)
        else:
            consumer.subscribe([TOPIC_ARTICLES_INGESTED])

        count = 0
        for message in consumer:
            payload = message.value
            if not isinstance(payload, dict):
                continue
            if payload.get("event") != EVENT_ARTICLE_INGESTED:
                continue
            yield payload
            count += 1
            if limit is not None and count >= limit:
                break
    finally:
        consumer.close()


def article_dict_from_event(event: dict[str, Any]) -> dict[str, Any]:
    """Convertit un événement Kafka en dict compatible parse_article()."""
    article: dict[str, Any] = {
        "feed_id": event["feed_id"],
        "url": event["url"],
        "s3_uri": event["s3_uri"],
        "content_hash": event["content_hash"],
        "title": None,
    }
    if event.get("feed_lang"):
        article["feed_lang"] = event["feed_lang"]
    return article
