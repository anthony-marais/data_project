# PressLake

Datalake presse (RSS → MinIO médaillon) puis chat sourcé (RAG).  
Le moteur est un **package Python** (`src/presslake`) ; les flux sont de la **config** (`config/feeds.yml`), pas du code.

Cadrage : [docs/README.md](docs/README.md) · parcours : [docs/learning-path.md](docs/learning-path.md).

## État

- [x] Package `presslake` (uv, `src/presslake`) + CI GitHub Actions
- [x] Compose : Postgres, MinIO, Redpanda, OpenSearch, Qdrant, Open WebUI
- [x] Ingest RSS → bronze MinIO + catalogue Postgres
- [x] Parser silver + contrats JSON Schema
- [x] FastAPI (catalogue, `/metrics`, retrieve, chat, `/v1` OpenAI-compat)
- [x] Observabilité (`presslake ops status`, alerte 6 h)
- [x] Bus Redpanda (`parse --from-kafka` / `--replay`)
- [x] OpenSearch BM25 + Qdrant (chunks citables)
- [x] RAG / chat (Ollama local + Open WebUI)
- [ ] Langfuse (module 13)
- [ ] MCP + SDK (module 14)
- [ ] Spark Scala (module 15)
- [ ] DVC + MLflow (module 16)

## Prérequis

- Docker Engine + plugin Compose
- [uv](https://docs.astral.sh/uv/) (`uv --version`)
- Python **3.14** (voir `.python-version`)
- Pour le chat : [Ollama](https://ollama.com/) sur l’hôte (`ollama serve` + `ollama pull llama3.2:1b`)

## Démarrage

```bash
cp .env.example .env
# renseigner les mots de passe (MinIO : 8 caractères minimum)

uv sync
docker compose up -d
docker compose ps   # tout healthy

uv run presslake db init
```

Pipeline quotidien (après ingest) :

```bash
uv run presslake poll
uv run presslake parse          # ou : parse --from-kafka
uv run presslake index
uv run presslake embed
```

Chat CLI et API + UI :

```bash
uv run presslake chat "De quoi parle le corpus aujourd'hui ?"
uv run presslake serve --host 0.0.0.0   # API :8000
# Lab module 12 : notebooks/12-rag-chat-exploration.ipynb
# Open WebUI : http://localhost:3000  (pointe vers PressLake /v1, pas Ollama)
```

Ollama CPU forcé (iGPU AMD instable) : `scripts/setup-ollama-cpu-only.sh`. GPU AMD : `scripts/setup-ollama-amd-gpu.sh` (test seulement).

## CLI

| Commande | Rôle |
|---|---|
| `presslake poll` | RSS → bronze + catalogue |
| `presslake parse` | bronze → silver |
| `presslake validate examples\|lake` | Contrats JSON Schema |
| `presslake index` / `search` | OpenSearch BM25 |
| `presslake embed` / `similar` | Chunks + Qdrant |
| `presslake retrieve` | Hybride BM25 + vecteur (sans LLM) |
| `presslake chat` | RAG sourcé (Ollama) |
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
| Ollama (hôte) | 11434 | LLM local |
| FastAPI (hôte) | 8000 | API + RAG |
