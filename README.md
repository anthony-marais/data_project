# PressLake

Datalake presse (RSS → MinIO médaillon) puis chat sourcé (RAG).  
Le moteur est un **package Python** (`src/presslake`) ; les flux sont de la **config** (`config/feeds.yml`), pas du code.

Cadrage : [docs/README.md](docs/README.md) · parcours : [docs/learning-path.md](docs/learning-path.md).

## État

- [x] Package `presslake` (uv, `src/presslake`) + CI GitHub Actions
- [x] Compose : Postgres, MinIO, Redpanda, OpenSearch, Qdrant, Open WebUI (+ profil `langfuse`)
- [x] Ingest RSS → bronze MinIO + catalogue Postgres
- [x] Parser silver + contrats JSON Schema
- [x] FastAPI (catalogue, `/metrics`, retrieve, chat, `/v1` OpenAI-compat)
- [x] Observabilité (`presslake ops status`, alerte 6 h)
- [x] Bus Redpanda (`parse --from-kafka` / `--replay`)
- [x] OpenSearch BM25 + Qdrant (chunks citables)
- [x] RAG / chat (Ollama local + Open WebUI)
- [x] Eval RAG + traces Langfuse (module 13, profil Compose `langfuse`)
- [x] MCP (outils `search` / `read`, `presslake mcp`)
- [ ] Spark Scala (module 15) — `presslake spark` (profil Compose `spark`)
- [ ] DVC + MLflow (module 16)

## Prérequis

- Docker Engine + plugin Compose
- [uv](https://docs.astral.sh/uv/) (`uv --version`)
- Python **3.14** (voir `.python-version`)
- Pour le chat : [Ollama](https://ollama.com/) sur l’hôte (`ollama serve` + `ollama pull llama3.2:1b`)

## Démarrage A→Z

Mode d'emploi commenté (toutes les commandes) :

```bash
uv run presslake guide
./scripts/presslake-a-to-z.sh --help
```

Enchaînement infra + ingest :

```bash
cp .env.example .env   # mots de passe (MinIO : 8 caractères minimum)
uv sync
./scripts/presslake-a-to-z.sh
```

Ou à la main : `docker compose up -d` puis `uv run presslake db init` puis `uv run presslake pipeline`.

```bash
cp .env.example .env
# renseigner les mots de passe (MinIO : 8 caractères minimum)

uv sync
docker compose up -d
docker compose ps   # tout healthy

uv run presslake db init
```

Pipeline quotidien (après ingest) — déjà lancé par `presslake pipeline` :

```bash
uv run presslake pipeline          # barre de progression (étape + %)
# uv run presslake pipeline --verbose
# uv run presslake pipeline --from-kafka --replay
```

Chat CLI et API + UI :

```bash
uv run presslake chat "De quoi parle le corpus aujourd'hui ?"
uv run presslake serve --host 0.0.0.0   # API :8000
# Lab module 12 : notebooks/12-rag-chat-exploration.ipynb
# Open WebUI : http://localhost:3000  (pointe vers PressLake /v1, pas Ollama)
# Eval RAG : uv run presslake eval --skip-llm
# Langfuse (optionnel) : docker compose --profile langfuse up -d  → :3100
# Lab module 13 : notebooks/13-langfuse-eval-exploration.ipynb
# MCP : uv run presslake mcp  (Cursor : .cursor/mcp.json)
# Lab module 14 : notebooks/14-mcp-sdk-exploration.ipynb
# Spark backfill (profil spark, pas le quotidien) : uv run presslake spark --build
# Lab module 15 : notebooks/15-spark-scala-exploration.ipynb
```

Ollama CPU forcé (iGPU AMD instable) : `scripts/setup-ollama-cpu-only.sh`. GPU AMD : `scripts/setup-ollama-amd-gpu.sh` (test seulement).

## CLI

| Commande | Rôle |
|---|---|
| `presslake guide` | Runbook A→Z, chaque commande commentée |
| `presslake pipeline` | `poll` → `parse` → `index` → `embed` |
| `presslake poll` | RSS → bronze + catalogue |
| `presslake parse` | bronze → silver |
| `presslake validate examples\|lake` | Contrats JSON Schema |
| `presslake index` / `search` | OpenSearch BM25 |
| `presslake embed` / `similar` | Chunks + Qdrant |
| `presslake retrieve` | Hybride BM25 + vecteur (sans LLM) |
| `presslake chat` | RAG sourcé (Ollama) |
| `presslake eval` | Jeu YAML retrieve / refus / citations (`--skip-llm`) |
| `presslake mcp` | Serveur MCP stdio (`search` + `read`) |
| `presslake spark` | Backfill Spark : silver JSON → gold parquet |
| `presslake serve` | FastAPI |
| `presslake ops status` | Dernière écriture ; code 1 si stale |
| `presslake db init` | Schéma catalogue + migrations |

`uv run presslake --help` pour les flags (`--lang`, `--recreate`, `--limit`, …).

## Infra locale

| Service | Port | Rôle |
|---|---|---|
| Postgres | 5432 | Catalogue |
| MinIO | 9000 / 9001 | Lake S3 (console :9001) |
| Redpanda | 19092 | Bus `article.ingested` |
| OpenSearch | 9200 | Recherche lexicale |
| Qdrant | 6333 | Recherche sémantique |
| Open WebUI | 3000 | Chat (via PressLake `/v1`) |
| Langfuse (profil `langfuse`) | 3100 | Traces eval RAG |
| Spark backfill (profil `spark`) | — | Job one-shot MinIO (pas de port) |
| Ollama (hôte) | 11434 | LLM local |
| FastAPI (hôte) | 8000 | API + RAG |
