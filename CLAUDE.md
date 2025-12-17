# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: Environment Management

**ALWAYS USE PIXI - NEVER USE SYSTEM PYTHON**

This project requires specific versions of PyTorch, JAX, CUDA libraries, and other dependencies that **must not** conflict with system packages. Using system Python will cause:
- CUDA version mismatches
- Package conflicts
- Import errors
- Broken dependencies

### Environment Strategy

**USE `dev` ENVIRONMENT BY DEFAULT** (99% of use cases):
```bash
pixi shell -e dev          # Enter dev environment
pixi run -e dev <command>  # Run command in dev environment
```

The `dev` environment includes:
- ✅ PyTorch 2.7 with CUDA 12.1
- ✅ JAX 0.5.3 with CUDA 12 support
- ✅ All training and inference dependencies
- ✅ Development tools (pytest, ruff, pre-commit, jupyter)
- ✅ All project packages (flax, transformers, orbax, etc.)

**ONLY use `rlds` environment for TensorFlow/RLDS data processing**:
```bash
pixi shell -e rlds         # Only when processing RLDS datasets
```

The `rlds` environment includes:
- ✅ TensorFlow 2.15
- ✅ TensorFlow Datasets
- ❌ NO JAX (incompatible ml-dtypes versions)

**Why separate environments?**
- JAX 0.5.3 requires `ml-dtypes >= 0.4.0`
- TensorFlow 2.15 requires `ml-dtypes < 0.3.0`
- These are fundamentally incompatible
- Most users only need JAX (training/inference), not TensorFlow

### Quick Decision Guide

| Task | Environment | Command |
|------|-------------|---------|
| Training models | `dev` | `pixi run -e dev train <config>` |
| Running inference | `dev` | `pixi run -e dev serve-policy ...` |
| Running tests | `dev` | `pixi run -e dev test` |
| Linting/formatting | `dev` | `pixi run -e dev lint-fix` |
| Converting to LeRobot format | `dev` | `pixi run -e dev python examples/...` |
| Processing RLDS datasets | `rlds` | `pixi run -e rlds python scripts/...` |

**Default to `dev` unless you explicitly need TensorFlow/RLDS.**

## Project Overview

openpi is Physical Intelligence's open-source repository for robotics vision-language-action (VLA) models. It contains three model families:
- **π₀**: Flow-based VLA model
- **π₀-FAST**: Autoregressive VLA using FAST action tokenizer
- **π₀.₅**: Upgraded π₀ with improved open-world generalization using knowledge insulation

The repository provides both JAX and PyTorch implementations, with base model checkpoints pre-trained on 10k+ hours of robot data and fine-tuned checkpoints for specific platforms (DROID, ALOHA, LIBERO).

## Development Commands

**⚠️ IMPORTANT: Always use pixi environments, never system Python!**

All commands below should be run inside the pixi environment:
```bash
pixi shell -e dev    # Enter development environment (RECOMMENDED)
# OR
pixi run -e dev <command>  # Run single command
```

### Environment Setup

**RECOMMENDED**: This project uses [Pixi](https://pixi.sh) for environment management, which provides better CUDA/GPU support than uv. See [PIXI_SETUP.md](PIXI_SETUP.md) for complete documentation.

**⚠️ CRITICAL**: Never use system Python! Always use pixi environments.

#### Using Pixi (REQUIRED for development)
```bash
# Clone with submodules
git clone --recurse-submodules git@github.com:Physical-Intelligence/openpi.git
git submodule update --init --recursive

# Install pixi (if not already installed)
curl -fsSL https://pixi.sh/install.sh | bash

# Install DEV environment (USE THIS FOR 99% OF TASKS)
pixi install -e dev
pixi run -e dev full-setup

# For PyTorch models, apply transformers patches
pixi run -e dev patch-transformers

# Enter the dev environment shell
pixi shell -e dev
```

**Environment Guidelines**:
- **`dev` (default)**: Use for all training, inference, testing, and development
  - Includes: PyTorch, JAX with CUDA, pytest, ruff, jupyter, all project deps
  - This is what you should use 99% of the time

- **`rlds`** (special case): ONLY use when processing RLDS/TensorFlow datasets
  - Includes: TensorFlow 2.15, TensorFlow Datasets
  - Does NOT include JAX (incompatible ml-dtypes versions)
  - Only needed for `examples/libero/convert_libero_data_to_lerobot.py` or similar RLDS scripts

- **`default`** (minimal): Runtime only, no dev tools (rarely used)

- **`full`**: Dev tools + TensorFlow, no JAX (rarely used)

**Never use system Python or create virtualenvs manually!** Pixi manages everything.

#### Using UV (Alternative)
```bash
# Install dependencies with uv
GIT_LFS_SKIP_SMUDGE=1 uv sync
GIT_LFS_SKIP_SMUDGE=1 uv pip install -e .
```

### Testing
```bash
# ⚠️ ALWAYS use dev environment
pixi run -e dev test                                        # Run all tests
pixi run -e dev test src/openpi/models/model_test.py        # Run specific file
pixi run -e dev test src/openpi/models/model_test.py::test_name  # Run specific test

# OR from inside pixi shell
pixi shell -e dev
pytest
pytest src/openpi/models/model_test.py

# UV (legacy, not recommended)
uv run pytest
```

### Linting and Formatting
```bash
# ⚠️ ALWAYS use dev environment
pixi run -e dev lint                # Check code with ruff
pixi run -e dev lint-fix            # Auto-fix linting issues
pixi run -e dev format              # Format code
pixi run -e dev format-check        # Check formatting
pixi run -e dev pre-commit-run      # Run all pre-commit hooks

# OR from inside pixi shell
pixi shell -e dev
ruff check .
ruff check --fix .
ruff format .

# UV (legacy, not recommended)
uv run ruff check --fix .
uv run ruff format .
```

### Training

#### JAX Training
```bash
# ⚠️ ALWAYS use dev environment (has JAX with CUDA)

# Compute normalization statistics first
pixi run -e dev compute-norm-stats --config-name <config_name>

# Run training (XLA_PYTHON_CLIENT_MEM_FRACTION=0.9 set automatically by pixi)
pixi run -e dev train <config_name> --exp-name=<experiment_name> --overwrite

# Example
pixi run -e dev train pi05_libero --exp-name=my_experiment

# OR from inside pixi shell
pixi shell -e dev
python scripts/train.py pi05_libero --exp-name=my_experiment

# UV (legacy, requires manual env var)
XLA_PYTHON_CLIENT_MEM_FRACTION=0.9 uv run scripts/train.py <config_name> --exp-name=<experiment_name>
```

#### PyTorch Training
```bash
# ⚠️ ALWAYS use dev environment (has PyTorch with CUDA)

# Single GPU
pixi run -e dev train-pytorch <config_name> --exp_name <run_name> --save_interval <interval>

# Multi-GPU with pixi
pixi run -e dev torchrun --standalone --nnodes=1 --nproc_per_node=<num_gpus> scripts/train_pytorch.py <config_name> --exp_name <run_name>

# OR from inside pixi shell
pixi shell -e dev
python scripts/train_pytorch.py <config_name> --exp_name <run_name>

# UV (legacy)
uv run scripts/train_pytorch.py <config_name> --exp_name <run_name>
```

### Inference

#### Policy Server
```bash
# ⚠️ ALWAYS use dev environment (has JAX for inference)

# Serve a trained policy checkpoint
pixi run -e dev serve-policy policy:checkpoint --policy.config=<config_name> --policy.dir=<checkpoint_path>

# Example
pixi run -e dev serve-policy policy:checkpoint --policy.config=pi05_droid --policy.dir=checkpoints/pi05_droid/my_experiment/20000

# OR from inside pixi shell
pixi shell -e dev
python scripts/serve_policy.py policy:checkpoint --policy.config=pi05_droid --policy.dir=checkpoints/...

# UV (legacy)
uv run scripts/serve_policy.py policy:checkpoint --policy.config=<config_name> --policy.dir=<checkpoint_path>
```

#### Convert JAX to PyTorch
```bash
# ⚠️ ALWAYS use dev environment

pixi run -e dev python examples/convert_jax_model_to_pytorch.py \
    --checkpoint_dir /path/to/jax/checkpoint \
    --config_name <config_name> \
    --output_path /path/to/converted/pytorch/checkpoint

# UV (legacy)
uv run examples/convert_jax_model_to_pytorch.py \
    --checkpoint_dir /path/to/jax/checkpoint \
    --config_name <config_name> \
    --output_path /path/to/converted/pytorch/checkpoint
```

#### RLDS Data Processing (SPECIAL CASE)
```bash
# ⚠️ ONLY for RLDS/TensorFlow data processing, use rlds environment
# This is the ONLY time you should NOT use dev environment

pixi run -e rlds python examples/libero/convert_libero_data_to_lerobot.py

# Most data conversion scripts use JAX/PyTorch, so use dev environment:
pixi run -e dev python examples/droid/convert_droid_to_lerobot.py
```

## Architecture Overview

### Module Structure

```
src/openpi/
├── models/          # Model implementations
│   ├── model.py     # Base model classes and interfaces (ModelType, BaseModel)
│   ├── pi0.py       # π₀ flow-based model
│   ├── pi0_fast.py  # π₀-FAST autoregressive model
│   ├── gemma.py     # Gemma language model integration
│   ├── siglip.py    # SigLIP vision encoder
│   └── tokenizer.py # Action tokenization
├── models_pytorch/  # PyTorch model implementations
│   ├── pi0_pytorch.py
│   └── gemma_pytorch.py
├── policies/        # Robot-specific policy wrappers
│   ├── policy.py           # Base Policy class
│   ├── droid_policy.py     # DROID robot platform
│   ├── aloha_policy.py     # ALOHA robot platform
│   └── libero_policy.py    # LIBERO benchmark
├── training/        # Training infrastructure
│   ├── config.py           # Training configurations (DataConfig, TrainConfig)
│   ├── data_loader.py      # LeRobot dataset loading
│   ├── optimizer.py        # Optimizer setup
│   ├── checkpoints.py      # Checkpoint management
│   └── weight_loaders.py   # Load weights from base models
├── serving/         # Policy server for remote inference
├── shared/          # Shared utilities
│   ├── download.py         # Checkpoint downloading from GCS
│   ├── normalize.py        # State/action normalization
│   ├── image_tools.py      # Image preprocessing
│   └── array_typing.py     # Type annotations
└── transforms.py    # Data transformation pipeline

scripts/
├── train.py                # JAX training script
├── train_pytorch.py        # PyTorch training script
├── compute_norm_stats.py   # Precompute normalization statistics
└── serve_policy.py         # Launch policy server

examples/
├── droid/          # DROID robot examples
├── aloha_real/     # Real ALOHA robot examples
├── aloha_sim/      # ALOHA simulation examples
├── libero/         # LIBERO benchmark examples
└── simple_client/  # Testing inference without robot
```

### Key Architecture Concepts

#### Model Types
Three model types defined in `models/model.py`:
- `PI0`: Flow matching-based action prediction
- `PI0_FAST`: Autoregressive action tokens using FSQ tokenizer
- `PI05`: Enhanced π₀ with knowledge insulation (flow matching head only)

#### Data Pipeline
1. **Raw data**: LeRobot datasets or RLDS format
2. **Repack transforms**: Convert dataset-specific format to common format
3. **Data transforms**: Robot-specific transformations (e.g., camera view mapping, action space changes)
4. **Normalization**: State/action normalization using precomputed statistics
5. **Model transforms**: Model-specific preprocessing (e.g., image resizing, tokenization)

The normalized data format is:
```python
{
    "image": {
        "base_0_rgb": float32[*b, 224, 224, 3],     # in [-1, 1]
        "left_wrist_0_rgb": ...,
        "right_wrist_0_rgb": ...,
    },
    "image_mask": {"base_0_rgb": bool[*b], ...},
    "state": float32[*b, s],                        # normalized state
    "tokenized_prompt": int32[*b, l],               # optional
    "actions": float32[*b, ah, ad],                 # normalized actions
}
```

#### Policies
Policies wrap models with robot-specific I/O handling:
- Define `Inputs` class: maps robot observations to model inputs
- Define `Outputs` class: maps model actions to robot commands
- Handle data transforms, normalization, and denormalization
- See `policies/libero_policy.py` for well-documented example

#### Configs
Training is configured through dataclasses in `training/config.py`:
- `DataConfig`: Dataset location, transforms, normalization
- `TrainConfig`: Hyperparameters, optimizer, model config
- Configs are registered in `_CONFIGS` dict and retrieved by name

#### Normalization Statistics
Critical for training stability. Statistics are precomputed using `scripts/compute_norm_stats.py` and stored as JSON in the checkpoint assets directory. Can be reloaded from base model checkpoints during fine-tuning to maintain consistency.

### JAX vs PyTorch

**JAX (default)**:
- Full feature support including π₀-FAST, FSDP, LoRA, EMA
- Mixed precision training by default (bfloat16 activations, float32 weights/gradients)
- Uses Flax NNX for model definition
- Checkpoint format: Orbax

**PyTorch (experimental)**:
- Supports π₀ and π₀.₅ models only
- Requires transformers library patches: `cp -r ./src/openpi/models_pytorch/transformers_replace/* .venv/lib/python3.11/site-packages/transformers/`
- Full precision training (bfloat16 or float32, no mixed precision yet)
- Multi-node training supported (unlike JAX)
- Checkpoint format: SafeTensors

### Checkpoint Management
- Base models downloaded from `gs://openpi-assets/checkpoints/<model_name>`
- Cached in `~/.cache/openpi` (or `$OPENPI_DATA_HOME`)
- Checkpoints auto-download on first use via `download.maybe_download()`

## Important Conventions

### Environment Usage (CRITICAL)

**DEFAULT TO `dev` ENVIRONMENT FOR ALL WORK**

```bash
# ALWAYS do this when working on the project
pixi shell -e dev

# OR prefix commands with
pixi run -e dev <command>
```

**Why?**
- Contains all necessary dependencies (PyTorch, JAX, CUDA)
- Includes development tools (pytest, ruff, jupyter)
- Works for training, inference, testing, and development
- Only exception: RLDS/TensorFlow data processing (use `rlds` environment)

**NEVER:**
- ❌ Use system Python (`python`, `python3`)
- ❌ Create manual virtualenvs (`python -m venv`)
- ❌ Install packages with system pip
- ❌ Use `conda` directly outside pixi
- ❌ Mix pixi and system packages

**Environment Decision Tree:**
```
Are you processing RLDS datasets with TensorFlow?
├─ YES → Use pixi shell -e rlds
└─ NO  → Use pixi shell -e dev (default for everything else)
```

### Testing
- Use pytest for all tests
- Test files end with `_test.py`
- Manual tests marked with `@pytest.mark.manual`

### Code Quality
- Python 3.11+ required
- Line length: 120 characters
- Import sorting: force single-line imports (except typing)
- Excluded from linting: `docker/`, `third_party/`, `src/openpi/models_pytorch/transformers_replace/`

### Environment Variables

**Pixi automatically sets these on activation:**
- `XLA_PYTHON_CLIENT_MEM_FRACTION=0.9`: JAX GPU memory usage
- `JAX_COMPILATION_CACHE_DIR=~/.cache/jax`: JAX compilation cache
- `OPENPI_DATA_HOME=~/.cache/openpi`: Checkpoint cache directory (customizable before activation)
- `GIT_LFS_SKIP_SMUDGE=1`: Skip LFS when installing LeRobot

**To override checkpoint cache location:**
```bash
export OPENPI_DATA_HOME=/data/openpi_models
pixi shell -e dev
```

**For UV (legacy), set manually:**
```bash
export XLA_PYTHON_CLIENT_MEM_FRACTION=0.9
export OPENPI_DATA_HOME=/custom/path  # Optional
export GIT_LFS_SKIP_SMUDGE=1
```

### Pixi Environment Reference

| Environment | Purpose | Contains JAX? | Contains TensorFlow? | When to Use |
|-------------|---------|---------------|---------------------|-------------|
| **dev** ⭐ | Development & Training | ✅ Yes | ❌ No | **DEFAULT - Use for 99% of tasks** |
| rlds | RLDS Data Processing | ❌ No | ✅ Yes | Only for TensorFlow/RLDS scripts |
| default | Runtime Only | ✅ Yes | ❌ No | Minimal installs (rare) |
| full | Dev + TensorFlow | ❌ No | ✅ Yes | Dev tools + TensorFlow (rare) |

**Why can't JAX and TensorFlow coexist?**
- JAX 0.5.3 requires `ml-dtypes >= 0.4.0`
- TensorFlow 2.15 requires `ml-dtypes < 0.3.0`
- These dependency ranges don't overlap (mathematical impossibility)
- Solution: Use separate environments for each

**Most users only need the `dev` environment** because:
- Training uses JAX ✅
- Inference uses JAX ✅
- Testing uses JAX/PyTorch ✅
- Data conversion typically uses JAX/PyTorch ✅
- Only RLDS-specific scripts need TensorFlow ⚠️

### GPU Requirements
- Inference: >8GB (RTX 4090)
- LoRA fine-tuning: >22.5GB (RTX 4090)
- Full fine-tuning: >70GB (A100 80GB / H100)
- Use `fsdp_devices` in config for model parallelism across multiple GPUs

### Data Formats
- Images: RGB uint8 [0, 255] or float32 [-1, 1], shape (H, W, 3)
- Standard image resolution: 224x224
- Required camera views: `base_0_rgb`, `left_wrist_0_rgb`, `right_wrist_0_rgb`
- State/actions: Normalized using quantile or z-score normalization

## Common Workflows

**⚠️ REMINDER: All workflows below assume you're using the `dev` environment**

### Adding Support for a New Robot
```bash
# 1. Enter dev environment
pixi shell -e dev

# 2. Create robot-specific policy in policies/<robot_name>_policy.py
# 3. Define Inputs class mapping robot observations to model format
# 4. Define Outputs class mapping model actions to robot commands
# 5. Create data config with appropriate transforms in training/config.py

# 6. Convert robot data to LeRobot format
python examples/<robot>/convert_<robot>_data_to_lerobot.py

# 7. Compute normalization stats
python scripts/compute_norm_stats.py --config-name <config>

# 8. Create training config in training/config.py
```

### Fine-tuning on New Dataset
```bash
# Always use dev environment for training
pixi shell -e dev

# 1. Convert data to LeRobot format
python examples/<dataset>/convert_to_lerobot.py

# 2. Create data config with robot-specific transforms (in training/config.py)

# 3. Compute norm stats
python scripts/compute_norm_stats.py --config-name <config>

# 4. Run training
python scripts/train.py <config> --exp-name=<name>

# 5. Serve policy
python scripts/serve_policy.py policy:checkpoint --policy.config=<config> --policy.dir=<checkpoint_dir>
```

### Remote Inference
Models can run on a separate server and stream actions via websocket. See `docs/remote_inference.md` for setup.

**All remote inference commands use the `dev` environment** (requires JAX for model loading).
