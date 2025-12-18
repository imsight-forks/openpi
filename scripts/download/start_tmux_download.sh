#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"

SUBDIR_TMP="tmp/openpi_checkpoints"
CACHE_DIR="${ROOT}/${SUBDIR_TMP}/cache"
LOG_DIR="${ROOT}/${SUBDIR_TMP}/logs"
LOG_FILE="${LOG_DIR}/download.$(date +%Y%m%d_%H%M%S).log"
SESSION="openpi-ckpt-dl"

# Default to the user's requested proxy; override with OPENPI_PROXY (empty disables).
DEFAULT_PROXY="http://127.0.0.1:7890"
OPENPI_PROXY="${OPENPI_PROXY:-${DEFAULT_PROXY}}"

mkdir -p "${CACHE_DIR}" "${LOG_DIR}"

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

export OPENPI_DATA_HOME="${CACHE_DIR}"

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

echo "Starting downloads in tmux session: ${SESSION}"
echo "  OPENPI_DATA_HOME=${OPENPI_DATA_HOME}"
echo "  log=${LOG_FILE}"
echo "  OPENPI_PROXY=${OPENPI_PROXY:-<disabled>}"

tmux new-session -d -s "${SESSION}" -n download
tmux send-keys -t "${SESSION}:download" "cd \"${ROOT}\"" C-m
tmux send-keys -t "${SESSION}:download" "echo \"OPENPI_DATA_HOME=${OPENPI_DATA_HOME}\" | tee -a \"${LOG_FILE}\"" C-m
tmux send-keys -t "${SESSION}:download" "env | rg -i '^(http|https|all|no)_proxy=' | tee -a \"${LOG_FILE}\" || true" C-m
tmux send-keys -t "${SESSION}:download" "pixi run -e dev python \"${ROOT}/scripts/download/download_all_checkpoints.py\" --gcs-token anon --clean-partials 2>&1 | tee -a \"${LOG_FILE}\"" C-m

# Split a monitor pane to watch disk usage and downloaded dirs.
tmux split-window -v -t "${SESSION}:download"
tmux send-keys -t "${SESSION}:download.1" "cd \"${ROOT}\"" C-m
tmux send-keys -t "${SESSION}:download.1" "while true; do clear; date; echo; du -sh \"${CACHE_DIR}\" 2>/dev/null || true; echo; ls -la \"${CACHE_DIR}/openpi-assets/checkpoints\" 2>/dev/null || true; sleep 10; done" C-m

echo
echo "Attach:"
echo "  tmux attach -t ${SESSION}"

