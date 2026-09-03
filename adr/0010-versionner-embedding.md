# ADR 0010 — Versionner l'embedding, pas le LLM

- Statut : accepted
- Date : 2026-09-04
- Décideurs : PressLake

## Contexte

`presslake embed --recreate` écrase Qdrant. Un changement de `EMBEDDING_MODEL` n'est pas comparable : pas de Recall@k, pas de rollback. Langfuse (13) évalue le **chat**, pas l'espace vectoriel.

## Décision

1. **params.yaml** (DVC) : `embed.model`, `embed.vector_size`, `embed.top_k` — source git des hyperparams.
2. **Recall@k** : fraction des cas `grounded` du jeu `rag-v1` avec ≥1 passage retrieve (`presslake recall`).
3. **MLflow** opt-in (`--mlflow` / `MLFLOW_ENABLED`) : runs locaux `mlruns/` (file store), pas un SaaS.
4. **Registre** `config/embed-registry.json` : dernier modèle « bon » ; `presslake recall --rollback` **affiche** les commandes (`embed --recreate`), il ne mute pas Qdrant tout seul.

Qdrant reste **une** collection `presslake-chunks`. Rollback = ré-embed avec le modèle du registre.

## Conséquences

- Changer de modèle = `params.yaml` + `.env` + `embed --recreate` (la dim est sondée au recreate).
- DVC ne stocke pas les poids ONNX (trop lourds, déjà chez HuggingFace / fastembed cache).
- Spark gold (15) n'est pas versionné ici.

## Alternatives rejetées

- **Deux collections Qdrant en parallèle** — plus tard si A/B live ; le lab compare des **runs** séquentiels.
- **MLflow tracking cloud** — même raison que Langfuse : opt-in local.
- **Versionner Ollama / le LLM** — le problème 16 est l'**index** sémantique.
