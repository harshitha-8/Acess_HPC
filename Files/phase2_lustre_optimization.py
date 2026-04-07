#!/usr/bin/env python3
"""
Lustre optimization helper for AgroGPT pipeline.
Python equivalent of phase2 Lustre setup shell script.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

DEFAULT_WORK_DIR = "/work/10904/harshitha114488/LLM-test"


def run_cmd(cmd: list[str], allow_fail: bool = False) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if not allow_fail and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def safe_setstripe(path: Path, count: int, stripe_size: str) -> None:
    rc, _, _ = run_cmd(
        ["lfs", "setstripe", "-c", str(count), "-S", stripe_size, str(path)],
        allow_fail=True,
    )
    if rc != 0:
        print("Note: Stripe config may require admin")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Lustre stripe settings for AgroGPT")
    parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR)
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    dataset_dir = work_dir / "Access"

    print("=== LUSTRE OPTIMIZATION FOR AGROGPT PIPELINE ===")
    print(f"Target: {dataset_dir}")
    print("")

    print("[1/3] Configuring stripe for image storage...")
    safe_setstripe(dataset_dir, count=4, stripe_size="4M")

    print("[2/3] Creating pipeline working directories...")
    cache_dir = work_dir / "processing" / "cache"
    models_dir = work_dir / "processing" / "models"
    results_dir = work_dir / "processing" / "results"

    cache_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    safe_setstripe(cache_dir, count=1, stripe_size="1M")
    safe_setstripe(results_dir, count=8, stripe_size="4M")

    print("[3/3] Verifying stripe configuration...")
    print("Dataset directory:")
    rc, out, _ = run_cmd(["lfs", "getstripe", str(dataset_dir)], allow_fail=True)
    if rc == 0 and out:
        lines = out.splitlines()[:5]
        for line in lines:
            print(line)

    print("")
    print("Setup complete. Ready for distributed inference.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
