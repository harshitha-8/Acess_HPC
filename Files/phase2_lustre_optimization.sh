#!/bin/bash
# Configure Lustre for optimal AgroGPT inference I/O

set -euo pipefail

WORK_DIR="/work/10904/harshitha114488/LLM-test"
DATASET_DIR="$WORK_DIR/Access"

echo "=== LUSTRE OPTIMIZATION FOR AGROGPT PIPELINE ==="
echo "Target: $DATASET_DIR"
echo ""

# 1. Set stripe for image directory (many medium-large files)
echo "[1/3] Configuring stripe for image storage..."
lfs setstripe -c 4 -S 4M "$DATASET_DIR" 2>/dev/null || echo "Note: Stripe config may require admin"

# 2. Create working directories with appropriate settings
echo "[2/3] Creating pipeline working directories..."
mkdir -p "$WORK_DIR/processing/cache"
mkdir -p "$WORK_DIR/processing/models"
mkdir -p "$WORK_DIR/processing/results"

lfs setstripe -c 1 -S 1M "$WORK_DIR/processing/cache" 2>/dev/null  # Small files
lfs setstripe -c 8 -S 4M "$WORK_DIR/processing/results" 2>/dev/null  # Large outputs

# 3. Verify configuration
echo "[3/3] Verifying stripe configuration..."
echo "Dataset directory:"
lfs getstripe "$DATASET_DIR" 2>/dev/null | head -5

echo ""
echo "Setup complete. Ready for distributed inference."
