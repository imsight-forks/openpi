from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def _find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "src").exists():
            return parent
    raise RuntimeError("Could not locate repo root (expected pyproject.toml and src/).")


def _parse_gs_url(url: str) -> tuple[str, str]:
    if not url.startswith("gs://"):
        raise ValueError(f"Expected gs:// URL, got: {url}")
    rest = url.removeprefix("gs://")
    bucket, _, prefix = rest.partition("/")
    if not bucket or not prefix:
        raise ValueError(f"Expected gs://<bucket>/<prefix>, got: {url}")
    return bucket, prefix.rstrip("/")


def _https_url(bucket: str, object_path: str) -> str:
    return f"https://storage.googleapis.com/{bucket}/{object_path}"


def main() -> int:
    repo_root = _find_repo_root(Path(__file__).resolve())

    parser = argparse.ArgumentParser(description="Download a gs:// checkpoint via aria2c using HTTPS URLs.")
    parser.add_argument(
        "--url",
        default="gs://openpi-assets/checkpoints/pi0_fast_droid",
        help="Checkpoint directory gs:// URL.",
    )
    parser.add_argument(
        "--data-home",
        type=Path,
        default=repo_root / "tmp" / "openpi_redownload_aria2" / "cache",
        help="Cache root (OPENPI_DATA_HOME-style).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=repo_root / "tmp" / "openpi_redownload_aria2" / "pi0_fast_droid",
        help="Directory for logs/manifest files.",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default="http://127.0.0.1:7890",
        help="Proxy URL for aria2c (set empty string to disable).",
    )
    parser.add_argument(
        "--clean-partials",
        action="store_true",
        help="Delete the local '<checkpoint>.partial' dir before downloading.",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=8,
        help="aria2c --max-concurrent-downloads",
    )
    parser.add_argument(
        "--max-conn-per-server",
        type=int,
        default=4,
        help="aria2c --max-connection-per-server",
    )
    parser.add_argument(
        "--split",
        type=int,
        default=4,
        help="aria2c --split",
    )
    args = parser.parse_args()

    bucket, prefix = _parse_gs_url(args.url)
    checkpoint_name = Path(prefix).name

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_home = args.data_home.expanduser().resolve()
    data_home.mkdir(parents=True, exist_ok=True)

    # Mirror openpi.shared.download's layout: <data_home>/<bucket>/<prefix>
    final_dir = (data_home / bucket / prefix).resolve()
    partial_dir = final_dir.with_suffix(".partial")

    if args.clean_partials and partial_dir.exists():
        shutil.rmtree(partial_dir)

    # List objects via gcsfs (metadata only), then download actual bytes via HTTPS+aria2.
    # Ensure gcsfs respects proxy env if present.
    import gcsfs  # noqa: PLC0415

    gcs_kwargs: dict[str, object] = {"token": "anon"}
    if any(os.getenv(k) for k in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]):
        gcs_kwargs["session_kwargs"] = {"trust_env": True}
    fs = gcsfs.GCSFileSystem(**gcs_kwargs)

    # gcsfs returns paths like "<bucket>/<object_path>".
    objects: list[str] = []
    for p in fs.find(f"{bucket}/{prefix}"):
        if p.endswith("/"):
            continue
        if not p.startswith(f"{bucket}/"):
            raise RuntimeError(f"Unexpected gcsfs path (expected '{bucket}/...'): {p}")
        objects.append(p.removeprefix(f"{bucket}/"))
    if not objects:
        raise RuntimeError(f"No objects found under: {args.url}")

    # Write an aria2 input file and pre-create directories.
    input_file = out_dir / "aria2.input.txt"
    mkdirs: set[Path] = set()
    lines: list[str] = []

    for object_path in sorted(objects):
        # object_path is like "checkpoints/pi0_fast_droid/params/..."
        rel = Path(object_path).relative_to(prefix)
        local_path = partial_dir / rel
        mkdirs.add(local_path.parent)
        lines.append(_https_url(bucket, object_path))
        lines.append(f"  dir={local_path.parent}")
        lines.append(f"  out={local_path.name}")
        lines.append("")

    for d in sorted(mkdirs):
        d.mkdir(parents=True, exist_ok=True)

    input_file.write_text("\n".join(lines))

    log_file = out_dir / f"aria2.{checkpoint_name}.log"
    manifest_file = out_dir / "manifest.json"

    aria2_cmd = [
        "aria2c",
        f"--input-file={input_file}",
        "--continue=true",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "--check-certificate=true",
        f"--max-concurrent-downloads={args.max_concurrent}",
        f"--max-connection-per-server={args.max_conn_per_server}",
        f"--split={args.split}",
        "--min-split-size=16M",
        "--summary-interval=10",
        f"--log={log_file}",
        "--log-level=notice",
    ]
    if args.proxy:
        aria2_cmd.append(f"--all-proxy={args.proxy}")

    print(f"Downloading {len(objects)} objects to: {partial_dir}")
    print(f"aria2 input: {input_file}")
    print(f"aria2 log:   {log_file}")
    print(f"proxy:       {args.proxy or '<disabled>'}")
    sys.stdout.flush()

    subprocess.run(aria2_cmd, check=True)

    # Basic validation: every expected local path exists.
    missing: list[str] = []
    for object_path in objects:
        rel = Path(object_path).relative_to(prefix)
        lp = partial_dir / rel
        if not lp.exists():
            missing.append(str(lp))

    payload = {
        "url": args.url,
        "data_home": str(data_home),
        "partial_dir": str(partial_dir),
        "final_dir": str(final_dir),
        "objects": len(objects),
        "missing": missing,
    }
    manifest_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote: {manifest_file}")

    if missing:
        print(f"Missing {len(missing)} files; not renaming partial dir.")
        return 2

    # Atomically promote the partial dir to the final checkpoint dir.
    if final_dir.exists():
        shutil.rmtree(final_dir)
    partial_dir.replace(final_dir)
    print(f"Promoted: {final_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
