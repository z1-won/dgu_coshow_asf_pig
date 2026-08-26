#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/bangjiwon/dev/pigproject"
DATASET_KEY="622"

# Start with the smallest keypoint source bundle that matches the validation track.
# Dataset 622 / Validation / source / keypoint / VS02.zip | 25 GB | filekey=533716
FILE_KEY="${1:-533716}"
OUTPUT_DIR="${2:-$PROJECT_ROOT/data/raw/aihub/622_source_smoke}"

cd "$PROJECT_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "ERROR: .venv not found. Run this inside $PROJECT_ROOT after project setup."
  exit 1
fi

source .venv/bin/activate

if [[ -z "${AIHUB_API_KEY:-}" ]]; then
  echo "ERROR: AIHUB_API_KEY is not set."
  echo 'Run: export AIHUB_API_KEY="your_real_aihub_api_key"'
  exit 1
fi

export AIHUBSHELL_BIN="${AIHUBSHELL_BIN:-$PROJECT_ROOT/bin/aihubshell}"

if [[ ! -x "$AIHUBSHELL_BIN" ]]; then
  echo "ERROR: AIHUBSHELL_BIN is not executable: $AIHUBSHELL_BIN"
  echo "Run: chmod +x $PROJECT_ROOT/bin/aihubshell"
  exit 1
fi

echo "Project: $PROJECT_ROOT"
echo "Dataset key: $DATASET_KEY"
echo "File key: $FILE_KEY"
echo "Output dir: $OUTPUT_DIR"
echo
echo "Disk space before download:"
df -h "$PROJECT_ROOT"
echo

mkdir -p "$OUTPUT_DIR"

echo "Downloading AI Hub source bundle..."
pig-aihub download \
  --dataset-key "$DATASET_KEY" \
  --file-key "$FILE_KEY" \
  --output-dir "$OUTPUT_DIR"

echo
echo "Downloaded files:"
find "$OUTPUT_DIR" -maxdepth 8 -type f | sort

echo
echo "Output size:"
du -sh "$OUTPUT_DIR"

echo
echo "Disk space after download:"
df -h "$PROJECT_ROOT"

