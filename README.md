# PressLake

Datalake presse (RSS → MinIO) puis chat sourcé (RAG).  
Le moteur est un **package Python** réinstallable ; les sources (flux) seront de la **config**, pas du code.

Cadrage : [docs/README.md](docs/README.md).

## État (à cocher au fil des étapes)

- [x] Package `presslake` (uv, `src/presslake`)
- [x] CI GitHub Actions — smoke `uv sync --frozen` + CLI  
- [ ] Compose : MinIO + Postgres **up** et healthy
- [ ] Bucket MinIO + premier objet bronze
- [ ] Ingest RSS
- [ ] Parser silver
- [ ] RAG / chat *(volontairement plus tard)*

## Prérequis

- Docker Engine + plugin Compose
- [uv](https://docs.astral.sh/uv/) (`uv --version`)

## Démarrage (aujourd’hui)

```bash
cp .env.example .env
# renseigner les mots de passe (MinIO : 8 caractères minimum)

uv sync
uv run presslake
# attendu : Hello from presslake!

docker compose up -d
docker compose ps