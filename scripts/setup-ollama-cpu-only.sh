#!/usr/bin/env bash
# Force Ollama en CPU uniquement — supprime le drop-in GPU et installe cpu-only.
# Usage : sudo ./scripts/setup-ollama-cpu-only.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_DROP_IN="/etc/systemd/system/ollama.service.d/amd-igpu.conf"
CPU_DROP_IN_SRC="${ROOT}/deploy/systemd/ollama-cpu-only.conf"
CPU_DROP_IN_DST="/etc/systemd/system/ollama.service.d/cpu-only.conf"
DROP_IN_DIR="/etc/systemd/system/ollama.service.d"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Relancer avec sudo : sudo $0"
  exit 1
fi

install -d "${DROP_IN_DIR}"

if [[ -f "${GPU_DROP_IN}" ]]; then
  rm -f "${GPU_DROP_IN}"
  echo "Supprimé : ${GPU_DROP_IN}"
fi

install -m 0644 "${CPU_DROP_IN_SRC}" "${CPU_DROP_IN_DST}"
echo "Installé : ${CPU_DROP_IN_DST}"

systemctl daemon-reload
systemctl restart ollama
sleep 3

echo ""
if journalctl -u ollama --no-pager -n 30 | grep -q 'library=cpu'; then
  echo "OK — Ollama démarre en mode CPU."
else
  echo "Vérifier : journalctl -u ollama -n 30 | grep inference"
fi

echo ""
echo "Test : ollama run llama3.2:1b ok && ollama ps"
echo "  → PROCESSOR doit être 100% CPU"
echo ""
echo ".env PressLake : OLLAMA_MODEL=llama3.2:1b"
echo "Puis redémarrer : pkill -f 'presslake serve' && uv run presslake serve --host 0.0.0.0 --port 8000"
