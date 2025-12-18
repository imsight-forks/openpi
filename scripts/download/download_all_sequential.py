from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time


def _find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "src").exists():
            return parent
    raise RuntimeError("Could not locate repo root (expected pyproject.toml and src/).")


def _read_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def _checkpoint_name(url: str) -> str:
    # Expect: gs://openpi-assets/checkpoints/<name>
    return url.rstrip("/").rsplit("/", 1)[-1]


def _maybe_copy_to_final(*, src_checkpoint_dir: Path, final_data_home: Path) -> Path:
    # src_checkpoint_dir is .../<data_home>/openpi-assets/checkpoints/<name>
    # final should mirror that.
    rel = src_checkpoint_dir.relative_to(src_checkpoint_dir.parents[2])  # openpi-assets/checkpoints/<name>
    dst = (final_data_home / rel).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--delete", f"{src_checkpoint_dir}/", f"{dst}/"], check=True)
    return dst


def main() -> int:
    repo_root = _find_repo_root(Path(__file__).resolve())

    parser = argparse.ArgumentParser(description="Download all checkpoints sequentially (continue on failures).")
    parser.add_argument(
        "--urls-file",
        type=Path,
        default=repo_root / "scripts" / "download" / "urls.txt",
        help="File with gs:// checkpoint URLs (one per line).",
    )
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Regex filter applied to URL (optional).",
    )
    parser.add_argument(
        "--data-home",
        type=Path,
        default=repo_root / "tmp" / "openpi_bulk_download" / "cache",
        help="Where to download checkpoints (OPENPI_DATA_HOME-style root).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=repo_root / "tmp" / "openpi_bulk_download",
        help="Where to write logs/manifests/results.json.",
    )
    parser.add_argument(
        "--final-data-home",
        type=Path,
        default=None,
        help="If set, rsync each successfully downloaded checkpoint into this OPENPI_DATA_HOME-style root.",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=os.getenv("OPENPI_PROXY", "http://127.0.0.1:7890"),
        help="Proxy URL for aria2c (empty disables).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=True,
        help="Always continue to next checkpoint even if one fails (default: true).",
    )
    args = parser.parse_args()

    urls = _read_urls(args.urls_file)
    if args.only:
        pattern = re.compile(args.only)
        urls = [u for u in urls if pattern.search(u)]

    if not urls:
        raise RuntimeError("No URLs selected.")

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    per_ckpt_dir = out_dir / "per_checkpoint"
    per_ckpt_dir.mkdir(parents=True, exist_ok=True)

    data_home = args.data_home.expanduser().resolve()
    data_home.mkdir(parents=True, exist_ok=True)

    if args.final_data_home is not None:
        final_data_home = args.final_data_home.expanduser().resolve()
        final_data_home.mkdir(parents=True, exist_ok=True)
    else:
        final_data_home = None

    results: dict[str, dict] = {}
    start_all = time.monotonic()

    downloader = (repo_root / "scripts" / "download" / "download_checkpoint_aria2.py").resolve()

    for i, url in enumerate(urls, start=1):
        name = _checkpoint_name(url)
        ckpt_out_dir = per_ckpt_dir / name
        ckpt_out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{i}/{len(urls)}] {url}")
        print(f"  out_dir={ckpt_out_dir}")
        print(f"  data_home={data_home}")

        cmd = [
            "python",
            "-u",
            str(downloader),
            "--url",
            url,
            "--data-home",
            str(data_home),
            "--out-dir",
            str(ckpt_out_dir),
            "--clean-partials",
        ]
        if args.proxy:
            cmd += ["--proxy", args.proxy]
        else:
            cmd += ["--proxy", ""]

        record: dict[str, object] = {
            "url": url,
            "name": name,
            "out_dir": str(ckpt_out_dir),
            "data_home": str(data_home),
            "proxy": args.proxy,
            "status": "unknown",
        }

        try:
            subprocess.run(cmd, check=True, cwd=str(repo_root))
            record["status"] = "downloaded"
            checkpoint_dir = (data_home / "openpi-assets" / "checkpoints" / name).resolve()
            record["checkpoint_dir"] = str(checkpoint_dir)
            if final_data_home is not None:
                copied_dir = _maybe_copy_to_final(src_checkpoint_dir=checkpoint_dir, final_data_home=final_data_home)
                record["final_checkpoint_dir"] = str(copied_dir)
                record["status"] = "downloaded_and_copied"
        except subprocess.CalledProcessError as e:
            record["status"] = "failed"
            record["error"] = {"returncode": e.returncode, "cmd": e.cmd}
            print(f"  !! failed: returncode={e.returncode}")
        except Exception as e:
            record["status"] = "failed"
            record["error"] = repr(e)
            print(f"  !! failed: {e!r}")

        results[url] = record
        (out_dir / "results.json").write_text(json.dumps({"results": results}, indent=2, sort_keys=True) + "\n")

    summary = {
        "urls": urls,
        "data_home": str(data_home),
        "final_data_home": str(final_data_home) if final_data_home is not None else None,
        "proxy": args.proxy,
        "elapsed_s": time.monotonic() - start_all,
        "downloaded": sum(1 for r in results.values() if r["status"] in {"downloaded", "downloaded_and_copied"}),
        "failed": sum(1 for r in results.values() if r["status"] == "failed"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"Wrote: {out_dir / 'results.json'}")
    print(f"Wrote: {out_dir / 'summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
