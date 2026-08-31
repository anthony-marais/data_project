-- Module 10 : langues feed (déclarée) et contenu (détectée).

ALTER TABLE articles ADD COLUMN IF NOT EXISTS feed_lang TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_lang TEXT;

CREATE INDEX IF NOT EXISTS idx_articles_content_lang ON articles (content_lang);
CREATE INDEX IF NOT EXISTS idx_articles_feed_lang ON articles (feed_lang);
