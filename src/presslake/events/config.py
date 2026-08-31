"""Configuration bus Kafka / Redpanda."""

import os

from dotenv import load_dotenv

load_dotenv()

CONSUMER_GROUP_PARSE = "presslake-parse"


def bootstrap_servers() -> list[str]:
    raw = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]
