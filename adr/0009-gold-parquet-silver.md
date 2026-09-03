# ADR 0009 — Gold = parquet silver, pas un second RAG

- Statut : accepted
- Date : 2026-09-04
- Décideurs : PressLake

## Contexte

L’architecture cible un préfixe MinIO `gold/`. Deux lectures possibles :

1. Ce que le **RAG** consomme (chunks + vecteurs) — aujourd’hui **Qdrant** (hot).
2. Ce qu’un **job volume** consomme (scan colonnaire, analytics, rejeu Spark).

Confondre les deux pousserait à dupliquer les embeddings dans S3 trop tôt (coût, drift vs Qdrant).

## Décision

Module 15 : **gold lake** = projection **parquet** du silver article :

```
s3://presslake/gold/layer=silver_parquet/feed_id=…/dt=…/*.parquet
```

- Une ligne = un article silver (même contrat + colonne `dt`).
- Les chunks / vecteurs restent Qdrant jusqu’au module 16 (versionning d’embeddings).
- Le chat et MCP **ne** lisent **pas** ce parquet.

Un futur `gold/model={embed}/…jsonl` (archi) reste possible : dump des chunks, pas le job 15.

## Conséquences

- `presslake spark` n’appelle ni OpenSearch ni Qdrant.
- Reconstruire le gold = relancer Spark (`overwrite` lab). En prod : overwrite de partition, pas tout le préfixe.
- Contrat JSON : `contracts/gold.v1.schema.json` (forme logique d’une ligne, pas le fichier parquet).

## Alternatives rejetées

- **Gold = copie des vecteurs** — prématuré sans DVC/MLflow (16).
- **Remplacer le silver JSON** — le parser Python et `read` MCP restent sur le JSON.
