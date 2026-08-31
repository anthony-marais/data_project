-- PressLake catalogue v1 — module 04
-- Inventaire des articles ingérés (pointeurs vers le bronze MinIO).

CREATE TABLE IF NOT EXISTS articles (
    id              BIGSERIAL PRIMARY KEY,
    feed_id         TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    item_key        TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    s3_uri          TEXT NOT NULL,
    title           TEXT,
    published_at    TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'fetched',
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT articles_feed_item_unique UNIQUE (feed_id, item_key),
    CONSTRAINT articles_status_check CHECK (
        status IN ('fetched', 'parsed', 'indexed', 'embedded')
    )
);

-- Requêtes fréquentes : par flux, par statut pipeline.
CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles (feed_id);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles (content_hash);
