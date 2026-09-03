#!/usr/bin/env bash
# Backfill silver JSON → gold parquet (module 15).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec uv run presslake spark "$@"
