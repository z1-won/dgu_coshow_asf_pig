#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/bangjiwon/dev/pigproject"
DATASET_KEY="71471"
OUTPUT_DIR="${1:-$PROJECT_ROOT/data/raw/aihub/71471}"

cd "$PROJECT_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "ERROR: .venv not found. Run project setup first."
  exit 1
fi

source .venv/bin/activate

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${AIHUB_API_KEY:-}" ]]; then
  echo "ERROR: AIHUB_API_KEY is not set in this shell."
  echo 'Run: export AIHUB_API_KEY="your_real_aihub_api_key"'
  exit 1
fi

export AIHUBSHELL_BIN="${AIHUBSHELL_BIN:-$PROJECT_ROOT/bin/aihubshell}"

if [[ ! -x "$AIHUBSHELL_BIN" ]]; then
  echo "ERROR: AIHUBSHELL_BIN is not executable: $AIHUBSHELL_BIN"
  echo "Run: chmod +x $PROJECT_ROOT/bin/aihubshell"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Cleaning stale 0-byte ZIP and part files..."
find "$OUTPUT_DIR" -type f -name '*.zip' -size 0 -print -delete
find "$OUTPUT_DIR" -type f -name '*.part*' -print -delete
echo

download_and_check() {
  local file_key="$1"
  local expected_name="$2"
  local description="$3"

  echo "Downloading: $description"
  pig-aihub download --dataset-key "$DATASET_KEY" --file-key "$file_key" --output-dir "$OUTPUT_DIR"

  local downloaded
  downloaded="$(find "$OUTPUT_DIR" -type f -name "$expected_name" -print -quit)"
  if [[ -z "$downloaded" ]]; then
    echo "ERROR: Expected file was not created: $expected_name"
    exit 1
  fi

  local bytes
  bytes="$(wc -c < "$downloaded" | tr -d ' ')"
  echo "Downloaded file size: $bytes bytes"
  if [[ "$bytes" == "0" ]]; then
    echo "ERROR: Downloaded file is 0 bytes: $downloaded"
    exit 1
  fi
  unzip -tq "$downloaded"
  echo "ZIP validation passed: $downloaded"
  echo
}

echo "Downloading AI Hub 71471 small metadata/keypoint label files..."
echo "Output dir: $OUTPUT_DIR"
echo

# 01.메타데이터.zip | 311 B | 511265
download_and_check 511265 "01.메타데이터.zip" "01.메타데이터.zip"

# TL_3.돼지_01.이미지_002.keypoints.zip | 28 MB | 511411
download_and_check 511411 "TL_3.돼지_01.이미지_002.keypoints.zip" "Training pig keypoints label"

# VL_3.돼지_01.이미지_002.keypoints.zip | 4 MB | 511459
download_and_check 511459 "VL_3.돼지_01.이미지_002.keypoints.zip" "Validation pig keypoints label"

echo
echo "Downloaded files:"
find "$OUTPUT_DIR" -maxdepth 8 -type f | sort

echo
echo "Output size:"
du -sh "$OUTPUT_DIR"

echo
echo "Validating downloaded ZIP files..."
ZERO_BYTE_FILES="$(find "$OUTPUT_DIR" -type f -name '*.zip' -size 0 -print)"
if [[ -n "$ZERO_BYTE_FILES" ]]; then
  echo "ERROR: The following ZIP files are 0 bytes:"
  echo "$ZERO_BYTE_FILES"
  echo "Delete the 0-byte files and rerun this script in the same shell where AIHUB_API_KEY is set."
  exit 1
fi

find "$OUTPUT_DIR" -type f -name '*.zip' -print0 | xargs -0 -n1 unzip -tq
echo "All ZIP files passed validation."
