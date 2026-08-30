"""Normalize the MDPI wearable biosensor (isolation vs. pair stress) dataset.

Source: `Supplementary File S1.csv` from the MDPI paper supplementary files --
one ~1Hz row per pig with heart rate, breath rate, core temperature, posture,
accelerometer and ECG channels, recorded while pigs were isolated or paired.

`SkinTemp` and `GSR` are dropped entirely: every row in the source file holds
the sensor's out-of-range sentinel value for both channels (-3276.8 and
65535.0), so there is no usable signal in either column. Other channels use
the same 16-bit sentinel convention (-3276.8, 6553.5, 65535.0, -128.0) for a
smaller fraction of rows; those cells are masked to NaN instead of dropping
the row. `heart_rate == 0` is also masked, since a live pig cannot have zero
heart rate -- it is the same kind of sensor dropout.

Condition labeling follows the paper's own published rule (see
`Supplementary Files S3 codes plots/S3_Q1.ipynb`, `categorize_activity`): a
row is `Pair` if the raw `Activity` label contains "pair" (case
insensitive), otherwise `Isolation`. The raw label mixes multiple test-block
tags (e.g. `bfandaf_isoandpair` contains both "iso" and "pair"), so it is not
a simple isolation/pair column on its own -- this substring rule is how the
source paper itself resolves it, and this module replicates it exactly for
consistency with the paper's own analysis.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


DATASET_KEY = "wearable_stress_biosensor"
DEFAULT_INPUT = "data/raw/external/wearable_stress_biosensor/Supplementary File S1.csv"
DEFAULT_PROCESSED_OUTPUT = "data/processed/wearable_stress_biosensor_features.csv"
DEFAULT_ARTIFACT_DIR = "artifacts/wearable_stress_biosensor_normalize"

RAW_TO_STANDARD = {
    "HR": "heart_rate",
    "BR": "breath_rate",
    "CoreTemp": "core_temp",
    "Posture": "posture_angle",
    "PeakAccel": "accel_peak",
    "Vertical": "accel_vertical",
    "Lateral": "accel_lateral",
    "Sagittal": "accel_sagittal",
    "ECGAmplitude": "ecg_amplitude",
    "ECGNoise": "ecg_noise",
    "RtoR": "rr_interval_ms",
    "HRV": "hrv",
    "BRAmplitude": "br_amplitude",
    "DeviceTemp": "device_temp",
}
FEATURE_COLUMNS = list(RAW_TO_STANDARD.values())
DROPPED_SOURCE_COLUMNS = ["SkinTemp", "GSR"]
SENTINEL_VALUES = {-3276.8, 6553.5, 65535.0, -128.0}
OUTPUT_COLUMNS = ["pig_id", "datetime", "condition", "raw_activity_label"] + FEATURE_COLUMNS


def load_source(path: str | Path) -> pd.DataFrame:
    usecols = ["Animal", "Time", "Activity", *RAW_TO_STANDARD.keys()]
    df = pd.read_csv(path, usecols=usecols)
    df = df.rename(columns=RAW_TO_STANDARD)
    df = df.rename(columns={"Animal": "pig_id", "Activity": "raw_activity_label"})
    df["datetime"] = pd.to_datetime(df["Time"], errors="coerce")
    df["pig_id"] = df["pig_id"].astype(str)
    df = df.dropna(subset=["datetime", "pig_id"]).drop(columns=["Time"])
    return df.sort_values(["pig_id", "datetime"]).reset_index(drop=True)


def mask_sentinels(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    columns = columns or FEATURE_COLUMNS
    out = df.copy()
    for col in columns:
        out.loc[out[col].isin(SENTINEL_VALUES), col] = np.nan
    out.loc[out["heart_rate"] <= 0, "heart_rate"] = np.nan
    return out


def add_condition(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["condition"] = np.where(
        out["raw_activity_label"].str.lower().str.contains("pair"), "Pair", "Isolation"
    )
    return out


def sentinel_summary(raw: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    columns = columns or FEATURE_COLUMNS
    rows = []
    for col in columns:
        sentinel_rows = int(raw[col].isin(SENTINEL_VALUES).sum())
        rows.append(
            {
                "feature": col,
                "sentinel_rows": sentinel_rows,
                "sentinel_pct": round(100 * sentinel_rows / len(raw), 2) if len(raw) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def write_report(
    output_dir: Path,
    raw: pd.DataFrame,
    cleaned: pd.DataFrame,
    sentinel_table: pd.DataFrame,
) -> Path:
    condition_counts = cleaned.groupby(["pig_id", "condition"]).size().unstack(fill_value=0)
    rows = [
        "# Wearable Stress Biosensor 정규화 보고서",
        "",
        f"- source rows: `{len(raw)}`",
        f"- pigs: `{cleaned['pig_id'].nunique()}`",
        f"- date range: `{cleaned['datetime'].min()}` ~ `{cleaned['datetime'].max()}`",
        f"- feature 수: `{len(FEATURE_COLUMNS)}`",
        f"- 제외한 원본 컬럼 (100% sentinel): {', '.join(DROPPED_SOURCE_COLUMNS)}",
        "",
        "## pig_id x condition row 수",
        "",
        dataframe_to_markdown(condition_counts.reset_index()),
        "",
        "## Sentinel 값 비율 (마스킹 후 NaN)",
        "",
        dataframe_to_markdown(sentinel_table),
        "",
        "## 판단",
        "",
        "- `condition`은 원 논문 코드(`categorize_activity`)와 동일하게 "
        "`raw_activity_label`에 \"pair\"가 포함되면 `Pair`, 아니면 `Isolation`으로 정의합니다.",
        "- `SkinTemp`, `GSR`은 원본 전체가 sensor sentinel 값이라 feature에서 제외했습니다.",
        "- 이 데이터는 71408/71763/622와 농장/돈방/기간 축이 겹치지 않으므로 "
        "메인 학습 데이터에 합치지 않고 별도 외부 검증 트랙으로 사용합니다.",
    ]
    report = output_dir / "wearable_stress_biosensor_normalize_report.md"
    report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return report


def build_stress_biosensor_dataset(
    input_path: str | Path = DEFAULT_INPUT,
    processed_output: str | Path = DEFAULT_PROCESSED_OUTPUT,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> pd.DataFrame:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    processed_path = Path(processed_output)
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    raw = load_source(input_path)
    cleaned = add_condition(mask_sentinels(raw))
    cleaned = cleaned[OUTPUT_COLUMNS]

    cleaned.to_csv(processed_path, index=False)
    cleaned.to_csv(artifact_path / "wearable_stress_biosensor_features.csv", index=False)

    summary = sentinel_summary(raw)
    summary.to_csv(artifact_path / "wearable_stress_biosensor_sentinel_summary.csv", index=False)
    write_report(artifact_path, raw, cleaned, summary)
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize the MDPI wearable stress biosensor CSV into the project's standard format."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--processed-output", default=DEFAULT_PROCESSED_OUTPUT)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cleaned = build_stress_biosensor_dataset(
        input_path=args.input,
        processed_output=args.processed_output,
        artifact_dir=args.artifact_dir,
    )
    print("rows:", len(cleaned))
    print("pigs:", cleaned["pig_id"].nunique())
    print(cleaned.groupby("condition").size())


if __name__ == "__main__":
    main()
