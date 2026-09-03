"""Texte du guide CLI A→Z (commentaires = ce que fait chaque commande)."""

GUIDE_TEXT = """
PressLake — de A à Z
====================
Préfixe partout :  uv run presslake <commande>
Aide d'une commande :  uv run presslake <commande> --help

------------------------------------------------------------------------
0. Une fois (machine)
------------------------------------------------------------------------

# Copier les secrets locaux (jamais commités). MinIO : mot de passe ≥ 8 car.
cp .env.example .env

# Installer le package + deps figées (lock).
uv sync

# iGPU AMD instable → forcer Ollama CPU (sudo, une fois).
# sudo ./scripts/setup-ollama-cpu-only.sh

# LLM local pour le chat (pas dans Docker).
# ollama serve          # souvent déjà en systemd
# ollama pull llama3.2:1b

------------------------------------------------------------------------
1. Infra Docker (Postgres, MinIO, Redpanda, OpenSearch, Qdrant, Open WebUI)
------------------------------------------------------------------------

# Démarrer l'infra. Open WebUI = :3000. Langfuse n'est PAS ici (profil séparé).
docker compose up -d

# Vérifier que les healthchecks passent (healthy / running).
docker compose ps

# Créer le bucket S3 langfuse si tu actives le profil plus tard (init déjà joué).
# docker compose up minio-init

------------------------------------------------------------------------
2. Catalogue Postgres
------------------------------------------------------------------------

# Applique schema.sql + migrations (idempotent). Obligatoire avant poll.
uv run presslake db init

------------------------------------------------------------------------
3. Pipeline quotidien  RSS → bronze → silver → BM25 → vecteurs
   Équivalent :  uv run presslake pipeline
------------------------------------------------------------------------

# Lire config/feeds.yml, fetch RSS, dédup, écrire bronze MinIO, upsert catalogue.
uv run presslake poll

# Extraire le texte (trafilatura / résumé RSS) → silver MinIO, statut parsed.
uv run presslake parse
# Variante bus : consommer topic Kafka au lieu du catalogue.
# uv run presslake parse --from-kafka
# Rejouer tout le topic depuis l'offset 0 (reconstruire le silver sans re-poll).
# uv run presslake parse --from-kafka --replay

# Contrats JSON Schema (exemples git, ou objets déjà dans le lake).
uv run presslake validate examples
# uv run presslake validate lake --limit 20

# Index lexical OpenSearch (BM25). --recreate si le mapping a changé.
uv run presslake index
# uv run presslake index --recreate

# Chunks + embeddings → Qdrant. --recreate si tu changes de modèle d'embed.
uv run presslake embed
# uv run presslake embed --recreate

------------------------------------------------------------------------
4. Vérifier (sans LLM)
------------------------------------------------------------------------

# BM25 seul (mots exacts, titre boosté).
uv run presslake search "Népal" --limit 5
# uv run presslake search "flood" --lang en

# Similarité cosine Qdrant (paraphrase).
uv run presslake similar "catastrophe himalayenne" --limit 5

# Hybride RRF (ce que le chat utilise). --raw = sans seuil cosine.
uv run presslake retrieve "Que dit le corpus sur le Népal ?" --limit 5
# uv run presslake retrieve "…" --bm25-only
# uv run presslake retrieve "…" --vector-only

# Santé ops : dernière écriture catalogue ; exit 1 si > 6 h sans write.
uv run presslake ops status

------------------------------------------------------------------------
5. Chat RAG + API + UI
------------------------------------------------------------------------

# One-shot CLI (Ollama). --retrieve-only = passages sans génération.
uv run presslake chat "Que dit le corpus sur le Népal ?"
# uv run presslake chat --retrieve-only "Népal"

# API FastAPI : catalogue, /retrieve, /chat, /v1 (Open WebUI), /metrics.
# --host 0.0.0.0 pour que le conteneur Open WebUI joigne l'hôte.
uv run presslake serve --host 0.0.0.0 --port 8000

# UI : http://localhost:3000  — base URL = http://host.docker.internal:8000/v1
# (pas Ollama direct, sinon pas de RAG)

------------------------------------------------------------------------
6. Eval (module 13)
------------------------------------------------------------------------

# Scores mécaniques retrieve / refus / citations, sans Ollama.
uv run presslake eval --skip-llm

# Pareil + génération Ollama + citations [1].
# uv run presslake eval

# Langfuse UI (opt-in, RAM ClickHouse). http://localhost:3100
# docker compose --profile langfuse up -d
# Dans .env : LANGFUSE_TRACING_ENABLED=true  puis  uv run presslake eval

------------------------------------------------------------------------
7. MCP (module 14) — agent Cursor / autre host
------------------------------------------------------------------------

# Serveur stdio (le host le lance ; stdout = JSON-RPC, pas de print).
uv run presslake mcp

# Outils sans protocole :
#   search = retrieve hybride ; read = silver MinIO (jamais bronze)

------------------------------------------------------------------------
8. Spark backfill (module 15) — PAS le quotidien
------------------------------------------------------------------------

# Job Scala : silver JSON MinIO → gold/layer=silver_parquet (colonnes, partitions).
# Première fois : construire l'image (sbt assembly, plusieurs minutes).
# uv run presslake spark --build
# uv run presslake spark
# uv run presslake spark --list

# Le chat / MCP ne lisent pas ce parquet. Voie volume seulement.

------------------------------------------------------------------------
9. Embeddings versionnés (module 16)
------------------------------------------------------------------------

# Recall@k sur les cas grounded (même jeu que eval).
# uv run presslake recall --write-metrics
# uv run presslake recall --register
# uv run presslake recall --rollback
# MLflow local : uv add mlflow && uv run presslake recall --mlflow
# UI : uv run mlflow ui --backend-store-uri ./mlruns

------------------------------------------------------------------------
Script shell (mêmes étapes, exécutable)
------------------------------------------------------------------------
  ./scripts/presslake-a-to-z.sh           # infra + db + pipeline ingest
  ./scripts/presslake-a-to-z.sh --help
""".strip()
