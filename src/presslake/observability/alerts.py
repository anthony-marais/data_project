"""
Alertes ops basées sur le catalogue Postgres.

Critère module 08 : alerter si aucune écriture depuis N heures (défaut 6).
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

from presslake.observability.catalog_metrics import refresh_metrics_from_postgres
from presslake.observability.catalog_queries import (
    get_articles_total,
    get_last_write_at,
    stale_threshold_seconds,
)


@dataclass(frozen=True)
class OpsStatus:
    """État ops lisible par /ops/status et la CLI."""

    last_write_at: datetime | None
    seconds_since_write: int | None
    stale_threshold_seconds: int
    stale: bool
    articles_total: int
    message: str


def evaluate_ops_status(conn: psycopg.Connection) -> OpsStatus:
    """
    Évalue l'état stale et synchronise les jauges Prometheus catalogue.

    La source de vérité est Postgres ; les jauges sont rafraîchies pour /metrics.
    """
    refresh_metrics_from_postgres(conn)

    threshold = stale_threshold_seconds()
    last_write = get_last_write_at(conn)
    total = get_articles_total(conn)

    if last_write is None:
        return OpsStatus(
            last_write_at=None,
            seconds_since_write=None,
            stale_threshold_seconds=threshold,
            stale=True,
            articles_total=total,
            message="Catalogue vide — aucune écriture enregistrée.",
        )

    if last_write.tzinfo is None:
        last_write = last_write.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = int((now - last_write).total_seconds())
    is_stale = delta > threshold

    if is_stale:
        hours = threshold // 3600
        message = (
            f"ALERTE : aucune écriture depuis {delta // 3600}h "
            f"(seuil {hours}h). Vérifier le worker poll."
        )
    else:
        message = "OK — ingest récent."

    return OpsStatus(
        last_write_at=last_write,
        seconds_since_write=delta,
        stale_threshold_seconds=threshold,
        stale=is_stale,
        articles_total=total,
        message=message,
    )
