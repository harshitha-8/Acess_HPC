#!/usr/bin/env python3
"""
Dataset structure assessment utility.
Python equivalent of the shell inventory report workflow.
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
import subprocess
import sys

DEFAULT_DATASET_BASE = "/work/10904/harshitha114488/LLM-test/Access"


def run_cmd(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def count_stage_dirs(dataset_base: Path, stage: str) -> int:
    stage = stage.lower()
    count = 0
    for root, dirs, _ in os.walk(dataset_base):
        _ = root
        for dname in dirs:
            if stage in dname.lower():
                count += 1
    return count


def image_format_distribution(dataset_base: Path) -> Counter[str]:
    valid_exts = {"jpg", "png", "tif"}
    counts: Counter[str] = Counter()

    for root, _, files in os.walk(dataset_base):
        for fname in files:
            if "." not in fname:
                continue
            ext = fname.rsplit(".", 1)[1].lower()
            if ext in valid_exts:
                counts[ext] += 1
    return counts


def sample_directories(dataset_base: Path, limit: int = 20) -> list[Path]:
    dirs: list[Path] = []
    for root, current_dirs, _ in os.walk(dataset_base):
        root_path = Path(root)
        depth = len(root_path.relative_to(dataset_base).parts) if root_path != dataset_base else 0
        if depth <= 3:
            dirs.append(root_path)

        if depth >= 3:
            current_dirs[:] = []

    return dirs[:limit]


def sample_metadata_files(dataset_base: Path, limit: int = 20) -> list[Path]:
    metadata_exts = {".json", ".csv", ".txt", ".xml"}
    files: list[Path] = []
    for root, _, names in os.walk(dataset_base):
        for name in names:
            path = Path(root) / name
            if path.suffix.lower() in metadata_exts:
                files.append(path)
                if len(files) >= limit:
                    return files
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Dataset inventory report")
    parser.add_argument("--dataset-base", default=DEFAULT_DATASET_BASE)
    args = parser.parse_args()

    dataset_base = Path(args.dataset_base)
    if not dataset_base.exists():
        print(f"Dataset not found: {dataset_base}", file=sys.stderr)
        return 1

    print("=== DATASET INVENTORY REPORT ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("")

    print("[1] Defoliation Stage Distribution:")
    pre_count = count_stage_dirs(dataset_base, "pre")
    post_count = count_stage_dirs(dataset_base, "post")
    print(f"Pre-defoliation folders: {pre_count}")
    print(f"Post-defoliation folders: {post_count}")

    print("")
    print("[2] Image Format Distribution:")
    fmt_counts = image_format_distribution(dataset_base)
    for ext in sorted(fmt_counts):
        print(f"{fmt_counts[ext]:>6} {ext}")

    print("")
    print("[3] Storage Consumption:")
    print(run_cmd(["du", "-sh", str(dataset_base)]))

    print("")
    print("[4] Directory Structure Sample:")
    for dpath in sample_directories(dataset_base, limit=20):
        print(dpath)

    print("")
    print("[5] Metadata Files Present:")
    for fpath in sample_metadata_files(dataset_base, limit=20):
        print(fpath)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
