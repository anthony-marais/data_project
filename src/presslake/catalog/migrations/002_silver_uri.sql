-- Module 05 : pointeur vers l'objet silver + suivi pipeline.

ALTER TABLE articles ADD COLUMN IF NOT EXISTS silver_s3_uri TEXT;
