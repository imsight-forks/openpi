#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"

# Default proxy (override with OPENPI_PROXY; set empty to disable).
DEFAULT_PROXY="http://127.0.0.1:7890"
OPENPI_PROXY="${OPENPI_PROXY:-${DEFAULT_PROXY}}"

# Where to write outputs (override with OPENPI_BULK_OUT_DIR).
TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OPENPI_BULK_OUT_DIR:-${ROOT}/tmp/openpi_bulk_download/${TS}}"
LOG_DIR="${OUT_DIR}/logs"
LOG_FILE="${LOG_DIR}/run.log"
DATA_HOME="${OUT_DIR}/cache"

# Optional: copy successful checkpoints into this cache (OPENPI_DATA_HOME-style root).
FINAL_DATA_HOME="${OPENPI_FINAL_DATA_HOME:-}"

SESSION="${OPENPI_TMUX_SESSION:-openpi-ckpt-dl-all}"

mkdir -p "${LOG_DIR}" "${DATA_HOME}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found; install it first." >&2
  exit 1
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "tmux session already exists: ${SESSION}" >&2
  echo "Attach with: tmux attach -t ${SESSION}" >&2
  exit 1
fi

cd "${ROOT}"

CMD=$(cat <<EOF
set -euo pipefail
cd "${ROOT}"
export PYTHONUNBUFFERED=1

if [[ -n "${OPENPI_PROXY}" ]]; then
  export http_proxy="${OPENPI_PROXY}"
  export https_proxy="${OPENPI_PROXY}"
  export all_proxy="${OPENPI_PROXY}"
  export HTTP_PROXY="${OPENPI_PROXY}"
  export HTTPS_PROXY="${OPENPI_PROXY}"
  export ALL_PROXY="${OPENPI_PROXY}"
  export no_proxy="localhost,127.0.0.1"
  export NO_PROXY="localhost,127.0.0.1"
fi

echo "OUT_DIR=${OUT_DIR}" | tee -a "${LOG_FILE}"
echo "DATA_HOME=${DATA_HOME}" | tee -a "${LOG_FILE}"
echo "FINAL_DATA_HOME=${FINAL_DATA_HOME:-<unset>}" | tee -a "${LOG_FILE}"
echo "OPENPI_PROXY=${OPENPI_PROXY:-<disabled>}" | tee -a "${LOG_FILE}"

ARGS=(
  --urls-file "${ROOT}/scripts/download/urls.txt"
  --data-home "${DATA_HOME}"
  --out-dir "${OUT_DIR}"
  --proxy "${OPENPI_PROXY}"
)
if [[ -n "${FINAL_DATA_HOME}" ]]; then
  ARGS+=(--final-data-home "${FINAL_DATA_HOME}")
fi

pixi run -e dev python -u "${ROOT}/scripts/download/download_all_sequential.py" "\${ARGS[@]}" 2>&1 | tee -a "${LOG_FILE}"
echo "DONE (exit=\$?)" | tee -a "${LOG_FILE}"
exec bash
EOF
)

MON=$(cat <<EOF
cd "${ROOT}"
while true; do
  clear
  date
  echo
  echo "SESSION=${SESSION}"
  echo "OUT_DIR=${OUT_DIR}"
  echo "DATA_HOME=${DATA_HOME}"
  echo "FINAL_DATA_HOME=${FINAL_DATA_HOME:-<unset>}"
  echo "OPENPI_PROXY=${OPENPI_PROXY:-<disabled>}"
  echo "LOG_FILE=${LOG_FILE}"
  echo
  du -sh "${DATA_HOME}" 2>/dev/null || true
  echo
  if [[ -f "${OUT_DIR}/summary.json" ]]; then
    echo "--- summary.json ---"
    cat "${OUT_DIR}/summary.json"
  fi
  echo
  echo "--- tail log ---"
  tail -n 40 "${LOG_FILE}" 2>/dev/null | sed 's/\\x1b\\[[0-9;]*m//g' || true
  sleep 10
done
EOF
)

tmux new-session -d -s "${SESSION}" -n download
tmux send-keys -t "${SESSION}:download" "${CMD}" C-m
tmux split-window -v -t "${SESSION}:download"
tmux send-keys -t "${SESSION}:download.1" "${MON}" C-m

echo "Started tmux session: ${SESSION}"
echo "Attach with: tmux attach -t ${SESSION}"
echo "Logs: ${LOG_FILE}"
echo "Outputs: ${OUT_DIR}"
