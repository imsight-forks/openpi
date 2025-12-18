# OpenPI checkpoint downloader

This folder contains helper scripts to download the public OpenPI checkpoints into a local cache directory using the
project Pixi environment.

## Environment

These scripts assume you’re running inside the Pixi `dev` environment.

```bash
pixi install -e dev
pixi run setup
```

## Quick start (tmux)

```bash
pixi run -e dev bash scripts/download/start_tmux_download.sh
tmux attach -t openpi-ckpt-dl
```

By default, downloads are written under:

- `tmp/openpi_checkpoints/cache` (also exported as `OPENPI_DATA_HOME`)
- progress logs under `tmp/openpi_checkpoints/logs`
- a summary JSON under `tmp/openpi_checkpoints/downloaded_paths.json`

## Proxy

The tmux launcher sets `http_proxy`, `https_proxy`, and `all_proxy` to `http://127.0.0.1:7890` by default.

Override with:

```bash
OPENPI_PROXY=http://127.0.0.1:7890 pixi run -e dev bash scripts/download/start_tmux_download.sh
```

Disable proxy:

```bash
OPENPI_PROXY= pixi run -e dev bash scripts/download/start_tmux_download.sh
```

## Direct run (no tmux)

```bash
OPENPI_DATA_HOME="$(pwd)/tmp/openpi_checkpoints/cache" \\
http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890 all_proxy=http://127.0.0.1:7890 \\
pixi run -e dev python scripts/download/download_all_checkpoints.py --gcs-token anon --clean-partials
```

## Using downloaded checkpoints (offline)

OpenPI resolves `gs://openpi-assets/...` via the local cache directory `OPENPI_DATA_HOME`. If the checkpoint already
exists on disk, OpenPI will use it without downloading.

### Recommended: centralized cache

If you copied the checkpoints to a centralized cache directory:

```bash
export OPENPI_DATA_HOME=/path/to/openpi_cache
```

Expected layout:

- `$OPENPI_DATA_HOME/openpi-assets/checkpoints/<checkpoint_name>/...`

### Example: load + run a single inference

```bash
export OPENPI_DATA_HOME=/path/to/openpi_cache
pixi run -e dev python scripts/infer_smoke_test.py \\
  --config pi0_fast_droid \\
  --checkpoint gs://openpi-assets/checkpoints/pi0_fast_droid \\
  --out-dir tmp/openpi_infer_smoke/pi0_fast_droid
```

### Example: serve a policy using local cache

```bash
export OPENPI_DATA_HOME=/path/to/openpi_cache
pixi run -e dev python scripts/serve_policy.py \\
  --policy.config pi0_fast_droid \\
  --policy.dir gs://openpi-assets/checkpoints/pi0_fast_droid \\
  --port 8000
```
