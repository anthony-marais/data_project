#!/usr/bin/env bash
# Active le GPU AMD intégré pour Ollama (ROCm) sur ThinkPad / APU Phoenix.
# Usage : ./scripts/setup-ollama-amd-gpu.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DROP_IN_SRC="${ROOT}/deploy/systemd/ollama-amd-igpu.conf"
DROP_IN_DIR="/etc/systemd/system/ollama.service.d"
DROP_IN_DST="${DROP_IN_DIR}/amd-igpu.conf"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Relancer avec sudo : sudo $0"
  exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama introuvable — installer depuis https://ollama.com"
  exit 1
fi

install -d "${DROP_IN_DIR}"
install -m 0644 "${DROP_IN_SRC}" "${DROP_IN_DST}"

# Accès /dev/dri pour sessions utilisateur (optionnel mais utile)
if id -nG ollama 2>/dev/null | grep -qw render; then
  echo "Utilisateur ollama déjà dans le groupe render."
else
  usermod -aG render,video ollama
fi

systemctl daemon-reload
systemctl restart ollama

echo ""
echo "Attente démarrage Ollama…"
sleep 3

if journalctl -u ollama --no-pager -n 40 | grep -q 'library=ROCm'; then
  echo "OK — Ollama utilise ROCm (GPU AMD)."
else
  echo "ATTENTION — GPU non détecté. Vérifier :"
  echo "  journalctl -u ollama -n 50 | grep -iE 'inference compute|ROCm|dropping'"
  echo "Sur gfx1103 (Radeon 780M), HSA_OVERRIDE_GFX_VERSION=11.0.0 est requis."
fi

echo ""
echo "Vérification : ollama ps  (PROCESSOR doit être GPU, pas 100% CPU)"
echo "Puis dans .env PressLake : OLLAMA_MODEL=llama3.2  (3B, confortable sur iGPU)"
