#!/bin/bash
# Pixi activation script for openpi

# Set JAX to use 90% of GPU memory for training
export XLA_PYTHON_CLIENT_MEM_FRACTION=0.9

# Set JAX compilation cache directory
export JAX_COMPILATION_CACHE_DIR="${HOME}/.cache/jax"

# Skip LFS when installing lerobot
export GIT_LFS_SKIP_SMUDGE=1

# Set default cache directory for openpi checkpoints
# Users can override this by setting OPENPI_DATA_HOME before activating
if [ -z "${OPENPI_DATA_HOME}" ]; then
    export OPENPI_DATA_HOME="${HOME}/.cache/openpi"
fi

echo "OpenPI environment activated"
echo "  XLA_PYTHON_CLIENT_MEM_FRACTION: ${XLA_PYTHON_CLIENT_MEM_FRACTION}"
echo "  OPENPI_DATA_HOME: ${OPENPI_DATA_HOME}"
