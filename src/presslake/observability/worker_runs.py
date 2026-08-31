"""
Journal des exécutions worker en Postgres.

Persiste poll/parse pour que /metrics reflète l'activité même quand
le worker tourne en CLI séparée de presslake serve.
"""

import psycopg

JOB_POLL = "poll"
JOB_PARSE = "parse"


def log_worker_run(
    conn: psycopg.Connection,
    job: str,
    *,
    new_items: int = 0,
    errors: int = 0,
) -> None:
    """
    Enregistre une exécution terminée (poll ou parse).

    Args:
        conn: connexion Postgres (commit à la charge de l'appelant si besoin).
        job: 'poll' ou 'parse'.
        new_items: articles ingérés ou parsés durant ce run.
        errors: nombre d'erreurs ignorées (parse skip, etc.).
    """
    conn.execute(
        """
        INSERT INTO worker_runs (job, new_items, errors)
        VALUES (%s, %s, %s)
        """,
        (job, new_items, errors),
    )


def get_worker_run_stats(conn: psycopg.Connection) -> list[dict]:
    """
    Agrégats par job pour les jauges Prometheus.

    Returns:
        Liste de {job, runs_total, new_items_total, errors_total, last_run_epoch}.
    """
    rows = conn.execute(
        """
        SELECT
            job,
            count(*)::int AS runs_total,
            coalesce(sum(new_items), 0)::int AS new_items_total,
            coalesce(sum(errors), 0)::int AS errors_total,
            extract(epoch FROM max(finished_at)) AS last_run_epoch
        FROM worker_runs
        GROUP BY job
        """
    ).fetchall()

    return [
        {
            "job": r[0],
            "runs_total": r[1],
            "new_items_total": r[2],
            "errors_total": r[3],
            "last_run_epoch": float(r[4]) if r[4] is not None else None,
        }
        for r in rows
    ]
