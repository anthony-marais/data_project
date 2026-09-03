#!/usr/bin/env bash
# PressLake — enchaînement A→Z (infra + ingest).
# Chaque ligne commentée au-dessus dit *pourquoi* on la lance.
#
# Usage (racine du repo) :
#   ./scripts/presslake-a-to-z.sh
#   ./scripts/presslake-a-to-z.sh --from-kafka
#   ./scripts/presslake-a-to-z.sh --skip-docker
#   ./scripts/presslake-a-to-z.sh --help
#
# Ne démarre pas `serve` (bloquant) ni Ollama : affiche les commandes à la fin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

SKIP_DOCKER=0
FROM_KAFKA=0
RECREATE=0

usage() {
  cat <<'EOF'
./scripts/presslake-a-to-z.sh [options]

  (défaut)     docker compose up + db init + poll + parse + index + embed
  --skip-docker   infra déjà up : seulement db init + pipeline
  --from-kafka    parse via Redpanda (parse --from-kafka) au lieu du catalogue
  --recreate      index --recreate et embed --recreate (mapping / modèle changé)
  --help          cette aide

Guide commenté (toutes les commandes, y compris chat / eval / Langfuse) :
  uv run presslake guide
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-docker) SKIP_DOCKER=1 ;;
    --from-kafka) FROM_KAFKA=1 ;;
    --recreate) RECREATE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Option inconnue : $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if [[ ! -f .env ]]; then
  echo "Pas de .env — copie depuis l'exemple puis renseigne les mots de passe :"
  echo "  cp .env.example .env"
  exit 1
fi

if [[ "${SKIP_DOCKER}" -eq 0 ]]; then
  # Infra locale : Postgres, MinIO, Redpanda, OpenSearch, Qdrant, Open WebUI.
  # Langfuse : ajouter --profile langfuse (volontairement hors du chemin quotidien).
  echo ">>> docker compose up -d"
  docker compose up -d
  echo ">>> docker compose ps"
  docker compose ps
fi

# Schéma catalogue (tables articles, worker_runs, …). Idempotent.
echo ">>> uv run presslake db init"
uv run presslake db init

# poll → parse → index → embed (bannières expliquées dans le CLI).
PIPE=(uv run presslake pipeline)
if [[ "${FROM_KAFKA}" -eq 1 ]]; then
  PIPE+=(--from-kafka)
fi
if [[ "${RECREATE}" -eq 1 ]]; then
  PIPE+=(--recreate)
fi
echo ">>> ${PIPE[*]}"
"${PIPE[@]}"

cat <<'EOF'

--- Suite (à lancer toi-même) ---

# Recherche sans LLM
uv run presslake retrieve "Népal"

# Chat RAG (Ollama doit tourner : ollama serve + ollama pull llama3.2:1b)
uv run presslake chat "Que dit le corpus sur le Népal ?"

# API + Open WebUI http://localhost:3000 (PressLake /v1, pas Ollama)
uv run presslake serve --host 0.0.0.0

# Eval retrieve / refus
uv run presslake eval --skip-llm

# Tout le mode d'emploi commenté
uv run presslake guide
EOF
