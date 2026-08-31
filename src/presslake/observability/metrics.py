"""
Métriques Prometheus in-process (compteurs worker).

Ces compteurs vivent en RAM du process qui exécute poll/parse.
Pour l'historique durable et /metrics via serve, voir worker_runs (Postgres)
et refresh_metrics_from_postgres().
"""

from prometheus_client import Counter

# Compteurs optionnels : utiles si poll/parse tournent dans le même process que serve.

POLL_RUNS = Counter(
    "presslake_poll_runs_total",
    "Exécutions poll dans CE processus (voir worker_runs_total pour l'historique Postgres).",
)

ARTICLES_INGESTED = Counter(
    "presslake_articles_ingested_total",
    "Articles ingérés dans CE processus.",
)

PARSE_RUNS = Counter(
    "presslake_parse_runs_total",
    "Exécutions parse dans CE processus.",
)

ARTICLES_PARSED = Counter(
    "presslake_articles_parsed_total",
    "Articles parsés dans CE processus.",
)

POLL_ERRORS = Counter(
    "presslake_poll_errors_total",
    "Erreurs poll dans CE processus.",
)

PARSE_ERRORS = Counter(
    "presslake_parse_errors_total",
    "Erreurs parse dans CE processus.",
)


def record_poll_finished(*, new_articles: int, errors: int = 0) -> None:
    """Incrémente les compteurs in-process (complément de worker_runs Postgres)."""
    POLL_RUNS.inc()
    if new_articles:
        ARTICLES_INGESTED.inc(new_articles)
    if errors:
        POLL_ERRORS.inc(errors)


def record_parse_finished(*, parsed: int, errors: int = 0) -> None:
    """Incrémente les compteurs in-process (complément de worker_runs Postgres)."""
    PARSE_RUNS.inc()
    if parsed:
        ARTICLES_PARSED.inc(parsed)
    if errors:
        PARSE_ERRORS.inc(errors)
