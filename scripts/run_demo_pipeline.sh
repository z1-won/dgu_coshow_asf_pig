#!/usr/bin/env bash
# Reproduce the canonical demo pipeline end to end, in one command.
#
# This exists because the project accumulated ~10 parallel artifact
# directories (bioenergy_split_v2, clean_baseline, clean_baseline_no_nh3,
# temperature_baseline, ...) built by running 10+ CLI commands by hand each
# time a core module changed (per-chamber scaler, per-pig aggregation,
# rolling features, threshold changes). That's fine for exploration but bad
# for "show me the code running": nobody -- including future us -- can
# reproduce the presented numbers from memory. This script is the one
# canonical path: run it, and artifacts/bioenergy_split_v2 +
# artifacts/bioenergy_clean_baseline end up in the exact state the pitch
# reports.
#
# Prerequisites: data/processed/aihub_71408_features.csv and
# aihub_71763_features.csv must already exist (see README.md "정규화" step
# -- these come from AI Hub downloads, not reproduced here).
#
# Usage: bash scripts/run_demo_pipeline.sh

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

INPUT_71408="data/processed/aihub_71408_features.csv"
INPUT_71763="data/processed/aihub_71763_features.csv"
SPLIT_DIR="artifacts/bioenergy_split_v2"
FINAL_DIR="artifacts/bioenergy_clean_baseline"
RULES="config/domain_rules.json"

for f in "$INPUT_71408" "$INPUT_71763"; do
  if [ ! -f "$f" ]; then
    echo "missing $f -- run the AI Hub normalize step first (see README.md)." >&2
    exit 1
  fi
done

# Rolling z-score columns (feedstuff/watersupply) are computed and saved to
# bioenergy_aggregated.csv either way, but excluded from the LSTM input --
# see docs/PROJECT... commit 90e3faf for why (mean/std/delta widened the
# threshold's bootstrap CI too much; zscore_3d alone did not).
ROLLING_EXCLUDES=(
  --exclude-feature feedstuff_volume_mean_roll_mean_3d
  --exclude-feature feedstuff_volume_mean_roll_std_3d
  --exclude-feature feedstuff_volume_mean_delta
  --exclude-feature watersupply_mean_roll_mean_3d
  --exclude-feature watersupply_mean_roll_std_3d
  --exclude-feature watersupply_mean_delta
)

echo "=== 1/2: bioenergy_split_v2 (per-chamber scaler, full validation split) ==="
pig-build-bioenergy \
  --input "$INPUT_71408" --input "$INPUT_71763" \
  --output-dir "$SPLIT_DIR" --seq-len 24 --min-val-windows 10 \
  "${ROLLING_EXCLUDES[@]}"
pig-train --artifact-dir "$SPLIT_DIR" --epochs 50 --batch-size 16
pig-threshold-compare --artifact-dir "$SPLIT_DIR" --percentiles 95 97 99 --consecutive-required 3
pig-detect --artifact-dir "$SPLIT_DIR" --percentile 97 --consecutive-required 3
pig-bioenergy-report --artifact-dir "$SPLIT_DIR" --seq-len 24

echo
echo "=== 2/2: bioenergy_clean_baseline (final demo model + domain rules) ==="
pig-build-clean-baseline \
  --input "$INPUT_71408" --input "$INPUT_71763" \
  --previous-detection-table "$SPLIT_DIR/bioenergy_detection_windows.csv" \
  --output-dir "$FINAL_DIR" --seq-len 24 --min-val-windows 10 \
  "${ROLLING_EXCLUDES[@]}"
pig-train --artifact-dir "$FINAL_DIR" --epochs 50 --batch-size 16
pig-detect --artifact-dir "$FINAL_DIR" --percentile 99 --consecutive-required 3
pig-bioenergy-report --artifact-dir "$FINAL_DIR" --seq-len 24
pig-explain-bioenergy --artifact-dir "$FINAL_DIR"
pig-baseline-overview --artifact-dir "$FINAL_DIR" --seq-len 24
pig-apply-rules --artifact-dir "$FINAL_DIR" --rules "$RULES" --seq-len 24

echo
echo "=== sanity check: pytest ==="
python -m pytest -q

echo
echo "=== done. key files for the demo ==="
echo "  $FINAL_DIR/bioenergy_detection_report.md       (모델 anomaly 결과)"
echo "  $FINAL_DIR/bioenergy_combined_alert_report.md  (모델+규칙 결합 disease_score 경보)"
echo "  $FINAL_DIR/bioenergy_pca_cluster_scatter.jpg    (정상 군집 시각화)"
echo "  $FINAL_DIR/bioenergy_error_scatter.jpg          (threshold 대비 오차 분포)"
echo "  $FINAL_DIR/threshold_confidence.csv             (부트스트랩 신뢰구간)"
