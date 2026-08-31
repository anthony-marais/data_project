"""Événements bus Kafka / Redpanda (module 09)."""

from presslake.events.config import CONSUMER_GROUP_PARSE
from presslake.events.consumer import article_dict_from_event, iter_article_ingested
from presslake.events.producer import EventProducer
from presslake.events.topics import TOPIC_ARTICLES_INGESTED

__all__ = [
    "CONSUMER_GROUP_PARSE",
    "EventProducer",
    "TOPIC_ARTICLES_INGESTED",
    "article_dict_from_event",
    "iter_article_ingested",
]
