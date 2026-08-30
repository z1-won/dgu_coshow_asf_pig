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
# The activity (622) track and the final cross-track ensemble step run only
# when data/processed/aihub_622_activity_timeseries_10min.csv is present --
# see README.md "행동량 feature를 10분 단위 시계열로 묶으려면". Without it
# the script still produces the full bioenergy pipeline on its own.
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

INPUT_ACTIVITY="data/processed/aihub_622_activity_timeseries_10min.csv"
ACTIVITY_DIR="artifacts/activity_model_10min"

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

if [ -f "$INPUT_ACTIVITY" ]; then
  echo
  echo "=== 3/3: activity_622 (behavior track) + final chamber ensemble ==="
  pig-build-activity-model --input "$INPUT_ACTIVITY" --output-dir "$ACTIVITY_DIR" --seq-len 24
  pig-train --artifact-dir "$ACTIVITY_DIR" --epochs 50 --batch-size 16
  pig-detect --artifact-dir "$ACTIVITY_DIR" --percentile 99 --consecutive-required 3
  pig-activity-report --artifact-dir "$ACTIVITY_DIR"
  pig-final-ensemble --bioenergy-dir "$FINAL_DIR" --activity-dir "$ACTIVITY_DIR"
else
  echo
  echo "=== 3/3: skipped (missing $INPUT_ACTIVITY -- see README.md for the 622 activity steps) ==="
fi

echo
echo "=== 4/4: external validation tracks (each skips if its raw data is missing) ==="

WEARABLE_RAW="data/raw/external/wearable_stress_biosensor/Supplementary File S1.csv"
WEARABLE_DIR="artifacts/wearable_stress_biosensor_sanity_check"
if [ -f "$WEARABLE_RAW" ]; then
  echo "--- Wearable Stress Biosensor ---"
  pig-normalize-stress-biosensor
  pig-build-stress-biosensor-dataset
  pig-train --artifact-dir "$WEARABLE_DIR" --epochs 100 --batch-size 16
  pig-evaluate-stress-biosensor
else
  echo "--- Wearable Stress Biosensor: skipped (missing $WEARABLE_RAW) ---"
fi

PRRSV_RAW="data/raw/external/prrsv_play_study/PRRSV_Play_study_Clinical_signs__rectal_temperature_and_medical_treatments.xlsx"
if [ -f "$PRRSV_RAW" ]; then
  echo "--- PRRSV Play Study ---"
  pig-prrsv-play-analysis
else
  echo "--- PRRSV Play Study: skipped (missing $PRRSV_RAW) ---"
fi

RFID_RAW="data/raw/external/rfid_lorawan_movement_17266727/MOVEMENT_Final.csv"
if [ -f "$RFID_RAW" ]; then
  echo "--- RFID-LoRaWAN movement baseline ---"
  pig-build-rfid-movement-features
else
  echo "--- RFID-LoRaWAN: skipped (missing $RFID_RAW) ---"
fi

FEEDING_5126661_RAW="data/raw/external/pig_feeding_behavior_5126661/feedingbehaviour.txt"
if [ -f "$FEEDING_5126661_RAW" ]; then
  echo "--- 5126661 feeding reference ---"
  pig-build-feeding-reference
else
  echo "--- 5126661 feeding reference: skipped (missing $FEEDING_5126661_RAW) ---"
fi

CLEARFARM_RAW_DIR="data/raw/external/clearfarm_growing_finishing"
CLEARFARM_PEN_DAY="data/processed/external/clearfarm/clearfarm_pen_day.csv"
CLEARFARM_BASELINE_DIR="artifacts/clearfarm_baseline"
if [ -d "$CLEARFARM_RAW_DIR" ]; then
  echo "--- ClearFarm (비육돈): rule validation + LSTM baseline ---"
  if [ ! -f "$CLEARFARM_PEN_DAY" ]; then
    pig-build-clearfarm-pen-day
  fi
  pig-validate-clearfarm-rules
  pig-build-clearfarm-baseline
  pig-train --artifact-dir "$CLEARFARM_BASELINE_DIR" --epochs 100 --batch-size 16
  pig-evaluate-clearfarm-baseline
else
  echo "--- ClearFarm: skipped (missing $CLEARFARM_RAW_DIR) ---"
fi

echo
echo "=== sanity check: pytest ==="
python -m pytest -q

echo
echo "=== ASF evidence summary (co-occurrence + real ASF ROC + HotPig) ==="
python scripts/build_asf_evidence_summary.py

echo
echo "=== done. key files for the demo ==="
echo "  $FINAL_DIR/ASF_EVIDENCE_SUMMARY.md              (제일 먼저 볼 문서 -- ASF 근거 전체 요약)"
echo "  $FINAL_DIR/bioenergy_detection_report.md       (모델 anomaly 결과)"
echo "  $FINAL_DIR/bioenergy_combined_alert_report.md  (모델+규칙 결합 disease_score 경보)"
echo "  $FINAL_DIR/bioenergy_pca_cluster_scatter.jpg    (정상 군집 시각화)"
echo "  $FINAL_DIR/bioenergy_error_scatter.jpg          (threshold 대비 오차 분포)"
echo "  $FINAL_DIR/threshold_confidence.csv             (부트스트랩 신뢰구간)"
if [ -f "$INPUT_ACTIVITY" ]; then
  echo "  $ACTIVITY_DIR/lstm_detection_report.md          (activity_622 track 단독 모델 결과)"
  echo "  artifacts/final_chamber_alert_report.md         (두 track 통합 최종 돈방 경보)"
  echo "  data/processed/final_chamber_anomaly_scores.csv (window 단위 통합 점수)"
fi
echo "  docs/00_overview/PROJECT_SCORECARD.md           (발표/심사용 한 장 요약, 전체 외부 검증 트랙 포함)"
if [ -d "$CLEARFARM_RAW_DIR" ]; then
  echo "  $CLEARFARM_BASELINE_DIR/clearfarm_baseline_detection_report.md (ClearFarm 비육돈 LSTM baseline)"
  echo "  artifacts/clearfarm_rule_validation/clearfarm_composite_rules_report.md (ClearFarm 규칙 검증 종합)"
fi
