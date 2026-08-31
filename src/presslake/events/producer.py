"""
Producteur Kafka pour les événements ingest.

Si KAFKA_BOOTSTRAP_SERVERS est absent ou vide, la publication est ignorée
(poll reste utilisable sans Redpanda).
"""

import json
from typing import Any

from kafka import KafkaProducer

from presslake.events.config import bootstrap_servers
from presslake.events.topics import TOPIC_ARTICLES_INGESTED

EVENT_ARTICLE_INGESTED = "article.ingested"


class EventProducer:
    """Producteur léger : un flush à la fermeture."""

    def __init__(self) -> None:
        servers = bootstrap_servers()
        self._enabled = bool(servers)
        self._producer: KafkaProducer | None = None

        if self._enabled:
            self._producer = KafkaProducer(
                bootstrap_servers=servers,
                key_serializer=lambda key: key.encode("utf-8"),
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                acks="all",
                linger_ms=5,
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def publish_article_ingested(
        self,
        *,
        feed_id: str,
        url: str,
        s3_uri: str,
        content_hash: str,
        item_key: str,
    ) -> None:
        """
        Publie un événement article.ingested sur presslake.articles.ingested.

        Clé Kafka = feed_id (ordre conservé par flux).
        """
        if not self._producer:
            return

        payload: dict[str, Any] = {
            "event": EVENT_ARTICLE_INGESTED,
            "feed_id": feed_id,
            "url": url,
            "s3_uri": s3_uri,
            "content_hash": content_hash,
            "item_key": item_key,
        }
        future = self._producer.send(
            TOPIC_ARTICLES_INGESTED,
            key=feed_id,
            value=payload,
        )
        future.get(timeout=10)

    def close(self) -> None:
        if self._producer:
            self._producer.flush()
            self._producer.close()
            self._producer = None

    def __enter__(self) -> "EventProducer":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
