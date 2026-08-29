#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/bangjiwon/dev/pigproject"
DATASET_KEY="71471"
OUTPUT_FILE="${1:-$PROJECT_ROOT/artifacts/aihub_71471_file_tree.txt}"

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

export AIHUBSHELL_BIN="${AIHUBSHELL_BIN:-$PROJECT_ROOT/bin/aihubshell}"

if [[ ! -x "$AIHUBSHELL_BIN" ]]; then
  echo "ERROR: AIHUBSHELL_BIN is not executable: $AIHUBSHELL_BIN"
  echo "Run: chmod +x $PROJECT_ROOT/bin/aihubshell"
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

echo "Recommended first downloads:"
pig-aihub recommended --dataset-key "$DATASET_KEY"

echo
echo "Saving AI Hub file tree to: $OUTPUT_FILE"
pig-aihub files --dataset-key "$DATASET_KEY" | tee "$OUTPUT_FILE"

echo
echo "Next: choose the smallest pig label/meta filekey from $OUTPUT_FILE, then run:"
echo "pig-aihub download --dataset-key $DATASET_KEY --file-key <filekey> --output-dir data/raw/aihub/$DATASET_KEY"
