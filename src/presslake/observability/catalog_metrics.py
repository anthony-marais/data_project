"""
Jauges catalogue et worker lues depuis Postgres au scrape /metrics.

Les compteurs in-process (record_poll_finished) restent utiles si worker et serve
partagent le même processus ; les jauges ci-dessous sont la source de vérité
persistante pour Prometheus.
"""

from datetime import datetime, timezone

import psycopg
from prometheus_client import Gauge

from presslake.observability.catalog_queries import (
    get_articles_total,
    get_last_write_at,
    stale_threshold_seconds,
)
from presslake.observability.worker_runs import get_worker_run_stats

# --- Catalogue (Postgres articles) ---

CATALOG_ARTICLES_TOTAL = Gauge(
    "presslake_catalog_articles_total",
    "Nombre total d'articles dans le catalogue Postgres.",
)

CATALOG_ARTICLES_BY_STATUS = Gauge(
    "presslake_catalog_articles",
    "Articles par statut pipeline (fetched, parsed, …).",
    ["status"],
)

LAST_WRITE_TIMESTAMP = Gauge(
    "presslake_last_write_timestamp",
    "Epoch Unix de la dernière écriture catalogue (max fetched_at).",
)

SECONDS_SINCE_LAST_WRITE = Gauge(
    "presslake_seconds_since_last_write",
    "Secondes depuis la dernière écriture catalogue.",
)

CATALOG_STALE = Gauge(
    "presslake_catalog_stale",
    "1 si aucune écriture catalogue depuis plus de PRESSLAKE_STALE_HOURS, sinon 0.",
)

# --- Worker runs (Postgres worker_runs) ---

WORKER_RUNS_TOTAL = Gauge(
    "presslake_worker_runs_total",
    "Nombre total d'exécutions worker enregistrées (poll ou parse).",
    ["job"],
)

WORKER_NEW_ITEMS_TOTAL = Gauge(
    "presslake_worker_new_items_total",
    "Somme des items traités par job (ingérés ou parsés).",
    ["job"],
)

WORKER_ERRORS_TOTAL = Gauge(
    "presslake_worker_errors_total",
    "Somme des erreurs enregistrées par job.",
    ["job"],
)

WORKER_LAST_RUN_TIMESTAMP = Gauge(
    "presslake_worker_last_run_timestamp",
    "Epoch Unix de la dernière exécution du job.",
    ["job"],
)


def _status_counts(conn: psycopg.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        """
        SELECT status, count(*)::int
        FROM articles
        GROUP BY status
        ORDER BY status
        """
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def refresh_metrics_from_postgres(conn: psycopg.Connection) -> None:
    """
    Met à jour toutes les jauges catalogue + worker depuis Postgres.

    Appelé juste avant generate_latest() sur GET /metrics et par ops/status.
    """
    # Catalogue
    total = get_articles_total(conn)
    CATALOG_ARTICLES_TOTAL.set(total)

    # Réinitialiser les labels connus puis appliquer l'état actuel.
    for status, count in _status_counts(conn):
        CATALOG_ARTICLES_BY_STATUS.labels(status=status).set(count)

    last_write = get_last_write_at(conn)
    threshold = stale_threshold_seconds()

    if last_write is None:
        LAST_WRITE_TIMESTAMP.set(0)
        SECONDS_SINCE_LAST_WRITE.set(-1)
        CATALOG_STALE.set(1)
    else:
        if last_write.tzinfo is None:
            last_write = last_write.replace(tzinfo=timezone.utc)
        delta = int((datetime.now(timezone.utc) - last_write).total_seconds())
        LAST_WRITE_TIMESTAMP.set(last_write.timestamp())
        SECONDS_SINCE_LAST_WRITE.set(delta)
        CATALOG_STALE.set(1 if delta > threshold else 0)

    # Worker runs
    for stats in get_worker_run_stats(conn):
        job = stats["job"]
        WORKER_RUNS_TOTAL.labels(job=job).set(stats["runs_total"])
        WORKER_NEW_ITEMS_TOTAL.labels(job=job).set(stats["new_items_total"])
        WORKER_ERRORS_TOTAL.labels(job=job).set(stats["errors_total"])
        if stats["last_run_epoch"] is not None:
            WORKER_LAST_RUN_TIMESTAMP.labels(job=job).set(stats["last_run_epoch"])
