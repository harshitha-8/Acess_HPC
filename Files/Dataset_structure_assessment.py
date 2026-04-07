#!/usr/bin/env python3
"""
Dataset structure assessment script for Acess_HPC project.
Analyzes pre/post-defoliation imagery dataset.
"""

import os
import json
from pathlib import Path
from datetime import datetime
import subprocess

DATASET_BASE = "/work/10904/harshitha114488/LLM-test/Access"


def main():
    print("=== DATASET INVENTORY REPORT ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Count pre vs post defoliation
    print("[1] Defoliation Stage Distribution:")
    pre_count = len(list(Path(DATASET_BASE).glob("**/[Pp]re*")))
    post_count = len(list(Path(DATASET_BASE).glob("**/[Pp]ost*")))
    print(f"Pre-defoliation folders: {pre_count}")
    print(f"Post-defoliation folders: {post_count}")

    # Count images by type
    print("\n[2] Image Format Distribution:")
    formats = {}
    for ext in [".jpg", ".png", ".tif"]:
        count = len(list(Path(DATASET_BASE).glob(f"**/*{ext}"))) + len(list(Path(DATASET_BASE).glob(f"**/*{ext.upper()}")))
        if count > 0:
            formats[ext] = count

    for fmt, count in sorted(formats.items()):
        print(f"{fmt}: {count}")

    # Get total volume
    print("\n[3] Storage Consumption:")
    result = subprocess.run(["du", "-sh", DATASET_BASE], capture_output=True, text=True)
    print(result.stdout.strip())

    # Directory structure
    print("\n[4] Directory Structure Sample:")
    for i, path in enumerate(sorted(Path(DATASET_BASE).glob("*/*"))):
        if i >= 20:
            break
        print(f"  {path.relative_to(DATASET_BASE)}")

    # Check for metadata
    print("\n[5] Metadata Files Present:")
    metadata_exts = [".json", ".csv", ".txt", ".xml"]
    for i, path in enumerate(Path(DATASET_BASE).glob("**/*")):
        if i >= 20:
            break
        if path.suffix.lower() in metadata_exts:
            print(f"  {path.relative_to(DATASET_BASE)}")


if __name__ == "__main__":
    main()
