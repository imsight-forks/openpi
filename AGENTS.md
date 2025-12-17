# Repository Guidelines

## Project Structure & Module Organization

- `src/openpi/`: main Python package (models, policies, training, serving, shared utilities).
- `packages/openpi-client/`: lightweight client library for websocket-based remote inference (`openpi-client`).
- `scripts/`: runnable entry points (training, serving, computing normalization stats).
- `examples/`: end-to-end usage for specific platforms (e.g., `examples/droid/`, `examples/aloha_*`, `examples/libero/`).
- `docs/`: focused guides (Docker, remote inference, normalization stats).
- `third_party/`: vendored code/submodules; avoid editing unless required.

## Build, Test, and Development Commands

Use Pixi for development. Never use system Python (`python`, `pip`)—run commands via `pixi run ...` or inside `pixi shell`.

Environments:
- `dev` (preferred): JAX/PyTorch runtime + tooling (pytest/ruff/pre-commit). `pixi install -e dev`
- `rlds`: TensorFlow/TFDS for RLDS data processing (separate to avoid JAX↔TF dependency conflicts). `pixi install -e rlds`
Use `dev` for training/inference; use `rlds` for TF-based RLDS tooling.

Setup:
- Submodules: `git submodule update --init --recursive`
- Install deps: `pixi install -e dev`
- Install workspace + git deps: `pixi run setup` (or `pixi run full-setup` to also install pre-commit hooks)
- (PyTorch) Patch transformers: `pixi run patch-transformers`

Day-to-day:
- Tests: `pixi run test` (or `pixi run test src/openpi/models/model_test.py`)
- Lint: `pixi run lint` / auto-fix: `pixi run lint-fix`
- Format: `pixi run format` / check: `pixi run format-check`
- Pre-commit: `pixi run pre-commit-run`

Common entry points:
- JAX training: `pixi run train <config_name> --exp-name=<name>`
- PyTorch training: `pixi run train-pytorch <config_name> --exp_name <name>`
- Serve a policy: `pixi run serve-policy policy:checkpoint --policy.config=<config> --policy.dir=<ckpt_dir>`

## Coding Style & Naming Conventions

- Python: 4-space indentation, max line length 120.
- Formatting/linting: Ruff is the source of truth (`ruff format`, `ruff check`); keep imports sorted (Ruff/isort config).
- Tests: name files `*_test.py` and test functions `test_*` close to the code they cover.

## Testing Guidelines

- Framework: `pytest` (configured to discover tests under `src/`, `scripts/`, and `packages/`).
- Use markers (e.g., `@pytest.mark.manual`) for tests that are slow, require GPUs, or depend on external datasets.

## Commit & Pull Request Guidelines

- Commits: follow Conventional Commit-style prefixes (e.g., `feat:`, `fix:`, `chore:`); include issue/PR refs when applicable (e.g., `(#123)`).
- PRs: include a clear description, reproduction/validation steps, and any relevant hardware/dataset notes; run `pre-commit`, `ruff`, and `pytest`, and add/update tests for behavior changes.

## Security & Configuration Tips

- Model assets are downloaded and cached (default `~/.cache/openpi`); override with `OPENPI_DATA_HOME`.
- Do not commit large artifacts (checkpoints, datasets, logs); keep paths configurable and update docs/examples when behavior changes.
