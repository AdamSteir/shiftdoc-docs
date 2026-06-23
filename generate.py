#!/usr/bin/env python3
"""
generate.py — calls ShiftDoc API for every feature file and writes PO + QAM JSON to the cache dir.

Usage:
    python generate.py <features_dir> [--cache-dir DIR] [--limit N] [--files stem1 stem2 ...]

    features_dir: path to the shiftdoc-tests/features directory

Examples:
    python generate.py ../shiftdoc-tests/features
    python generate.py ../shiftdoc-tests/features --cache-dir _cache_local/
    python generate.py ../shiftdoc-tests/features --files espresso bdd --cache-dir _cache_local/
"""

import json
import sys
import time
from pathlib import Path

import requests

SHIFTDOC_API = "https://shiftdoc-backend.onrender.com/analysis/run"
ROLES = ["product_owner", "qa_manager"]
ROLE_SLUG = {"product_owner": "po", "qa_manager": "qam"}
SLEEP_SECONDS = 7
REQUEST_TIMEOUT = 60
SKIP_DIRS = {"smoke"}
MAX_CONSECUTIVE_ERRORS = 5


def find_feature_files(features_dir: Path) -> list[Path]:
    files = []
    for f in sorted(features_dir.rglob("*.feature")):
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        files.append(f)
    return files


def cache_path(feature_file: Path, features_dir: Path, role_slug: str, cache_dir: Path) -> Path:
    rel = feature_file.relative_to(features_dir)
    filename = f"shiftdoc-{role_slug}-{feature_file.stem}.json"
    return cache_dir / rel.parent / filename


def call_shiftdoc(content: str, filename: str, role: str) -> dict:
    payload = {
        "test_format": "bdd",
        "role": role,
        "content": content,
        "filename": filename,
    }
    response = requests.post(SHIFTDOC_API, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return data.get("json_payload") or {}


def main():
    args = sys.argv[1:]

    cache_dir = Path(__file__).parent / "_cache_local"

    if "--cache-dir" in args:
        idx = args.index("--cache-dir")
        cache_dir = Path(args[idx + 1])
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    limit = None
    if "--limit" in args:
        idx = args.index("--limit")
        limit = int(args[idx + 1])
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    if not args:
        print("Usage: python generate.py <features_dir> [--cache-dir DIR] [--limit N] [--files ...]")
        sys.exit(1)

    features_dir = Path(args[0]).resolve()
    if not features_dir.exists():
        print(f"Error: features directory not found: {features_dir}")
        sys.exit(1)

    only_files = []
    if "--files" in args:
        idx = args.index("--files")
        only_files = args[idx + 1:]
        args = args[:idx]

    feature_files = find_feature_files(features_dir)
    if only_files:
        feature_files = [f for f in feature_files if any(o in str(f) for o in only_files)]
        print(f"(--files: processing {len(feature_files)} matched files)")
    elif limit:
        feature_files = feature_files[:limit]
        print(f"(--limit {limit}: processing first {limit} files only)")

    total = len(feature_files) * len(ROLES)
    call_num = 0
    errors = []
    consecutive_errors = 0
    suite_start = time.monotonic()

    print(f"Found {len(feature_files)} feature files -- {total} API calls at {SLEEP_SECONDS}s apart")
    print(f"Estimated time: ~{(total * SLEEP_SECONDS) // 60} minutes\n")

    for feature_file in feature_files:
        content = feature_file.read_text(encoding="utf-8")

        for role in ROLES:
            call_num += 1
            slug = ROLE_SLUG[role]
            out_path = cache_path(feature_file, features_dir, slug, cache_dir)
            rel_label = feature_file.relative_to(features_dir)
            print(f"[{call_num}/{total}] {rel_label} ({slug})")

            call_start = time.monotonic()
            try:
                result = call_shiftdoc(content, feature_file.name, role)
                elapsed = time.monotonic() - call_start
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(f"  saved -> {cache_dir.name}/{out_path.relative_to(cache_dir)} ({elapsed:.1f}s)")
                consecutive_errors = 0
            except Exception as e:
                elapsed = time.monotonic() - call_start
                print(f"  ERROR ({elapsed:.1f}s): {e}")
                errors.append({"file": str(rel_label), "role": slug, "error": str(e)})
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"\nAborting -- {MAX_CONSECUTIVE_ERRORS} consecutive failures. API may be down.")
                    break

            if call_num < total:
                time.sleep(SLEEP_SECONDS)

        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            break

    total_elapsed = time.monotonic() - suite_start
    mins, secs = divmod(int(total_elapsed), 60)
    print(f"\nDone. {total - len(errors)}/{total} succeeded in {mins}m {secs}s.")
    if errors:
        print(f"\n{len(errors)} errors:")
        for err in errors:
            print(f"  {err['file']} ({err['role']}): {err['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
