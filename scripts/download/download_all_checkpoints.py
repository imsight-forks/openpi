from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.parse

try:
    import openpi.shared.download as download
except ImportError:  # pragma: no cover
    _repo_root = None
    for parent in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (parent / "pyproject.toml").exists() and (parent / "src").exists():
            _repo_root = parent
            break
    if _repo_root is None:
        raise
    sys.path.insert(0, str(_repo_root / "src"))
    import openpi.shared.download as download


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


def _local_target_paths(data_home: Path, url: str) -> tuple[Path, Path]:
    parsed = urllib.parse.urlparse(url)
    local_path = data_home.expanduser().resolve() / parsed.netloc / parsed.path.strip("/")
    local_path = local_path.resolve()
    return local_path, local_path.with_suffix(".partial")


def main() -> int:
    here = Path(__file__).resolve()
    repo_root = _find_repo_root(here)

    default_data_home = repo_root / "tmp" / "openpi_checkpoints" / "cache"
    default_urls_file = repo_root / "scripts" / "download" / "urls.txt"
    default_out_json = repo_root / "tmp" / "openpi_checkpoints" / "downloaded_paths.json"

    parser = argparse.ArgumentParser(description="Download OpenPI checkpoints into a local cache directory.")
    parser.add_argument(
        "--data-home", type=Path, default=default_data_home, help="Target cache dir (OPENPI_DATA_HOME)."
    )
    parser.add_argument("--urls-file", type=Path, default=default_urls_file, help="File with gs:// checkpoint URLs.")
    parser.add_argument("--only", type=str, default="", help="Regex filter applied to URL (optional).")
    parser.add_argument("--force", action="store_true", help="Re-download even if already cached.")
    parser.add_argument(
        "--gcs-token",
        type=str,
        default="anon",
        help="GCS auth token (use 'anon' for public buckets; empty to use default credentials).",
    )
    parser.add_argument(
        "--clean-partials",
        action="store_true",
        help="Remove any existing '*.partial' download dirs before starting.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Python logging level (e.g., DEBUG, INFO).",
    )
    parser.add_argument("--out-json", type=Path, default=default_out_json, help="Write URL→local-path map here.")
    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, force=True)
    logging.getLogger("fsspec").setLevel(log_level)
    logging.getLogger("gcsfs").setLevel(log_level)

    os.environ["OPENPI_DATA_HOME"] = str(args.data_home.expanduser().resolve())
    args.data_home.mkdir(parents=True, exist_ok=True)

    proxies = {
        k: os.getenv(k)
        for k in [
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "no_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
        ]
    }
    active_proxies = {k: v for k, v in proxies.items() if v}
    print(f"OPENPI_DATA_HOME={os.environ['OPENPI_DATA_HOME']}")
    print(f"Proxies: {active_proxies or 'none detected in env'}")

    urls = _read_urls(args.urls_file)
    if args.only:
        pattern = re.compile(args.only)
        urls = [u for u in urls if pattern.search(u)]

    if not urls:
        print("No URLs selected (check --urls-file and --only).")
        return 1

    results: dict[str, str] = {}
    failures: dict[str, str] = {}

    gcs_token = args.gcs_token.strip()
    gcs_kwargs: dict[str, object] = {}
    if gcs_token:
        gcs_kwargs["token"] = gcs_token
    # gcsfs uses aiohttp; it only honors *_proxy env vars when trust_env=True.
    if any(os.getenv(k) for k in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]):
        gcs_kwargs["session_kwargs"] = {"trust_env": True}

    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] {url}")
        try:
            if args.clean_partials and url.startswith("gs://"):
                local_path, scratch_path = _local_target_paths(args.data_home, url)
                if scratch_path.exists():
                    print(f"  cleaning: {scratch_path}")
                    if scratch_path.is_dir():
                        shutil.rmtree(scratch_path)
                    else:
                        scratch_path.unlink()
                # If a previous run left the final path in a bad state, rely on --force.
                if local_path.exists() and args.force:
                    print(f"  will overwrite existing: {local_path}")

            kwargs = gcs_kwargs if url.startswith("gs://") else {}
            local_path = download.maybe_download(url, force_download=args.force, **kwargs)
            results[url] = str(local_path)
            print(f"  -> {local_path}")
        except Exception as e:
            failures[url] = repr(e)
            print(f"  !! failed: {e!r}")

    payload = {"data_home": os.environ["OPENPI_DATA_HOME"], "downloaded": results, "failed": failures}
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote: {args.out_json}")

    if failures:
        print(f"Failures: {len(failures)}/{len(urls)}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
