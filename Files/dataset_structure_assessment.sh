#!/bin/bash
set -euo pipefail

DATASET_BASE="/work/10904/harshitha114488/LLM-test/Access"

echo "=== DATASET INVENTORY REPORT ==="
echo "Timestamp: $(date -Iseconds)"
echo ""

# Count pre vs post defoliation
echo "[1] Defoliation Stage Distribution:"
find "$DATASET_BASE" -type d \( -name "*Pre*" -o -name "*pre*" \) | wc -l | xargs echo "Pre-defoliation folders:"
find "$DATASET_BASE" -type d \( -name "*Post*" -o -name "*post*" \) | wc -l | xargs echo "Post-defoliation folders:"

# Count images by type
echo ""
echo "[2] Image Format Distribution:"
find "$DATASET_BASE" -type f \( -iname "*.jpg" -o -iname "*.png" -o -iname "*.tif" \) | sed 's/.*\.//' | tr '[:upper:]' '[:lower:]' | sort | uniq -c

# Get total volume
echo ""
echo "[3] Storage Consumption:"
du -sh "$DATASET_BASE"

# Sample directory structure
echo ""
echo "[4] Directory Structure Sample:"
find "$DATASET_BASE" -maxdepth 3 -type d | head -20

# Check for existing metadata
echo ""
echo "[5] Metadata Files Present:"
find "$DATASET_BASE" -type f \( -name "*.json" -o -name "*.csv" -o -name "*.txt" -o -name "*.xml" \) | head -20
