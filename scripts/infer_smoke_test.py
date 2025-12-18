import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


def _find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "src").exists():
            return parent
    raise RuntimeError("Could not locate repo root (expected pyproject.toml and src/).")


def _ensure_import_paths(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root / "src"))
    sys.path.insert(0, str(repo_root / "packages" / "openpi-client" / "src"))


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_ensure_import_paths(_REPO_ROOT)

from openpi.policies import aloha_policy  # noqa: E402
from openpi.policies import droid_policy  # noqa: E402
from openpi.policies import libero_policy  # noqa: E402
from openpi.policies import policy_config as _policy_config  # noqa: E402
from openpi.training import config as _config  # noqa: E402


def _summarize_array(arr: np.ndarray) -> dict:
    arr = np.asarray(arr)
    summary: dict[str, object] = {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
    }
    if arr.size:
        finite = np.isfinite(arr)
        if finite.any():
            summary.update(
                min=float(arr[finite].min()),
                max=float(arr[finite].max()),
                mean=float(arr[finite].mean()),
            )
        summary["num_nan"] = int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0
        summary["num_inf"] = int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0
    return summary


def _summarize_tree(tree: dict) -> dict:
    out: dict[str, object] = {}
    for k, v in tree.items():
        if isinstance(v, dict):
            out[k] = _summarize_tree(v)
        elif isinstance(v, (np.ndarray, np.generic)):
            out[k] = _summarize_array(np.asarray(v))
        else:
            out[k] = {"type": type(v).__name__}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Load a checkpoint and run a single inference for a smoke test.")
    parser.add_argument("--config", default="pi0_fast_droid", help="Training config name (e.g., pi0_fast_droid).")
    parser.add_argument(
        "--checkpoint",
        default="gs://openpi-assets/checkpoints/pi0_fast_droid",
        help="Checkpoint directory (gs://... or local path).",
    )
    parser.add_argument(
        "--data-home",
        default="/data2/llm-models/openpi",
        help="OPENPI_DATA_HOME to use (should contain openpi-assets/...).",
    )
    parser.add_argument(
        "--out-dir",
        default="tmp/openpi_infer_smoke",
        help="Directory to write outputs to.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--runs", type=int, default=1, help="Number of timed inference runs (after warmup).")
    parser.add_argument("--warmup", type=int, default=1, help="Number of warmup inference runs.")
    args = parser.parse_args()

    out_dir = (_REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    os.environ["OPENPI_DATA_HOME"] = str(Path(args.data_home).expanduser().resolve())

    np.random.seed(args.seed)

    train_config = _config.get_config(args.config)
    policy = _policy_config.create_trained_policy(train_config, args.checkpoint)

    if "droid" in args.config:
        example = droid_policy.make_droid_example()
    elif "libero" in args.config:
        example = libero_policy.make_libero_example()
    else:
        example = aloha_policy.make_aloha_example()

    # Warmup (compilation / caches).
    for _ in range(max(0, args.warmup)):
        _ = policy.infer(example)

    timings_ms: list[float] = []
    last_outputs: dict | None = None
    for _ in range(max(1, args.runs)):
        start = time.monotonic()
        last_outputs = policy.infer(example)
        timings_ms.append((time.monotonic() - start) * 1000)

    assert last_outputs is not None
    actions = np.asarray(last_outputs.get("actions"))
    np.save(out_dir / "actions.npy", actions)

    summary = {
        "config": args.config,
        "checkpoint": args.checkpoint,
        "OPENPI_DATA_HOME": os.environ["OPENPI_DATA_HOME"],
        "out_dir": str(out_dir),
        "timings_ms": timings_ms,
        "inputs_summary": _summarize_tree(example),
        "outputs_summary": _summarize_tree(
            {k: v for k, v in last_outputs.items() if k in {"actions", "policy_timing", "state"}}
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    print(f"Wrote: {(out_dir / 'actions.npy')}")
    print(f"Wrote: {(out_dir / 'summary.json')}")
    print(f"actions: shape={actions.shape} dtype={actions.dtype} min={actions.min():.4f} max={actions.max():.4f}")
    print(f"timings_ms: {timings_ms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
