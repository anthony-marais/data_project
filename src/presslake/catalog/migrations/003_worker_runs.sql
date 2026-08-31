-- Module 08 : historique des exécutions worker (poll / parse).
-- Source de vérité pour les métriques ops lues au scrape /metrics.

CREATE TABLE IF NOT EXISTS worker_runs (
    id           BIGSERIAL PRIMARY KEY,
    job          TEXT NOT NULL,
    finished_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    new_items    INT NOT NULL DEFAULT 0,
    errors       INT NOT NULL DEFAULT 0,

    CONSTRAINT worker_runs_job_check CHECK (job IN ('poll', 'parse'))
);

CREATE INDEX IF NOT EXISTS idx_worker_runs_job_finished
    ON worker_runs (job, finished_at DESC);
