#!/usr/bin/env python3
"""
reconcile.py — removes stale cache entries that have no matching feature file.

Run after generate on pipeline commits. Deletes cache files whose source
feature file no longer exists in shiftdoc-tests/features/.

Usage:
    python reconcile.py --cache-dir _cache/ --features-dir shiftdoc-tests/features
"""

import sys
from pathlib import Path

SKIP_DIRS = {"smoke"}
ROLE_SLUGS = {"po", "qam"}


def find_feature_stems(features_dir: Path) -> set[tuple[str, str]]:
    stems = set()
    for f in features_dir.rglob("*.feature"):
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        rel = f.relative_to(features_dir)
        parent = rel.parent.as_posix()
        parent = "" if parent == "." else parent
        stems.add((parent, f.stem))
    return stems


def main():
    args = sys.argv[1:]

    cache_dir = Path("_cache")
    features_dir = Path("shiftdoc-tests/features")

    if "--cache-dir" in args:
        idx = args.index("--cache-dir")
        cache_dir = Path(args[idx + 1])
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    if "--features-dir" in args:
        idx = args.index("--features-dir")
        features_dir = Path(args[idx + 1]).resolve()

    if not cache_dir.exists():
        print("Cache directory does not exist, nothing to reconcile.")
        return

    if not features_dir.exists():
        print(f"Error: features directory not found: {features_dir}")
        sys.exit(1)

    feature_stems = find_feature_stems(features_dir)
    deleted = []

    for json_file in sorted(cache_dir.rglob("shiftdoc-*.json")):
        parts = json_file.stem.split("-", 2)  # ["shiftdoc", "po", "feature_stem"]
        if len(parts) != 3 or parts[1] not in ROLE_SLUGS:
            continue
        feature_stem = parts[2]
        rel_parent = json_file.parent.relative_to(cache_dir).as_posix()
        rel_parent = "" if rel_parent == "." else rel_parent

        if (rel_parent, feature_stem) not in feature_stems:
            print(f"  stale: {json_file.relative_to(cache_dir)} -> deleting")
            json_file.unlink()
            deleted.append(str(json_file))

    if deleted:
        print(f"\nReconcile: deleted {len(deleted)} stale cache entries.")
    else:
        print("Reconcile: cache is clean, no stale entries found.")


if __name__ == "__main__":
    main()
