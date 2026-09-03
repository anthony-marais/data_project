# ADR 0004 — Un seul moteur JVM : Spark batch

- Statut : accepted
- Date : 2026-09-04
- Décideurs : PressLake

## Contexte

Le poll RSS Python tient le quotidien. Un backfill (re-parse historique, projection colonnaire, migration de schéma) sur des milliers d’objets MinIO saturerait le worker item-par-item.

Les fiches visent aussi une brique JVM. Flink et Spark ensemble = deux runtimes à opérer.

## Décision

**Spark 3.x Scala** pour la **voie volume** uniquement.

- Lecture : `s3a://…/silver/` (JSON, partitions `source=` / `dt=`).
- Écriture : `s3a://…/gold/layer=silver_parquet/` (parquet, `partitionBy(feed_id, dt)`).
- Pas de `presslake poll` dans Spark. Pas de Flink.

Le job tourne en one-shot Compose (`profil spark`), pas dans `docker compose up -d` quotidien.

## Conséquences

- Python reste le chemin nominal (poll → parse → index → embed).
- RAG / MCP continuent de lire OpenSearch + Qdrant + silver JSON, pas le parquet gold.
- Un second moteur streaming (Flink) seulement si un besoin sub-seconde hors RSS apparaît (hors parcours).

## Alternatives rejetées

- **PySpark dans le package `presslake`** — le module 15 est explicitement Scala / JVM.
- **Spark tous les 5 min** — latence RSS déjà couverte par le poll ; Spark = batch.
- **Réécrire le parser en Scala** — le silver Python (trafilatura) reste la source ; Spark **projette**.
