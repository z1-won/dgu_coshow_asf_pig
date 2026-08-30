"""Build model-ready Wearable Stress Biosensor sanity-check data.

Takes the per-second table from `wearable_stress_biosensor_normalize.py`,
resamples it to the project's standard 10-minute window format, and builds
`Pair` (normal baseline) train/validation arrays plus an `Isolation` (stress)
test array for the existing LSTM autoencoder CLIs (`pig-train`, `pig-detect`).

`Pair` is treated as the normal baseline and `Isolation` as the stress
condition to detect, mirroring how HOTPIG (TN/HS) and Behavior x Heat
Tolerance (TN/HS) are already used in this project: a paired pig is in its
ordinary social housing, while an isolated pig is the condition the source
paper itself studies as a stressor.

Like Behavior x Heat Tolerance, this dataset is between-subject for at least
one animal (`pig11` has zero `Pair` rows in the source file), so a
per-animal scaler would leave that animal unscorable. A pooled `Pair`
scaler is used instead, fit once and applied to `Pair` validation and
`Isolation` test rows alike.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.bioenergy_pipeline import create_sequences
from pigproject.wearable_stress_biosensor_normalize import FEATURE_COLUMNS as RAW_FEATURE_COLUMNS


DATASET_KEY = "wearable_stress_biosensor"
DEFAULT_INPUT = "data/processed/wearable_stress_biosensor_features.csv"
DEFAULT_PROCESSED_OUTPUT = "data/processed/wearable_stress_biosensor_timeseries_10min.csv"
DEFAULT_ARTIFACT_DIR = "artifacts/wearable_stress_biosensor_sanity_check"
RESAMPLE_FREQ = "10min"
# The recordings are 11 separate short sessions (a few hours each) spread
# over about a month, not one continuous stream: bioenergy's 24-step (4h)
# window leaves too few 10-min bins per pig to both train and validate. 12
# steps (2h) is the largest window that still clears train/val windows for
# every pig at DEFAULT_TRAIN_RATIO, based on the smallest pig's Pair rows.
DEFAULT_SEQ_LEN = 12
DEFAULT_TRAIN_RATIO = 0.7

STD_FEATURES = ["heart_rate", "breath_rate", "hrv", "rr_interval_ms"]
MEAN_FEATURE_COLUMNS = [f"{col}_mean" for col in RAW_FEATURE_COLUMNS]
STD_FEATURE_COLUMNS = [f"{col}_std" for col in STD_FEATURES]
FEATURE_COLUMNS = MEAN_FEATURE_COLUMNS + STD_FEATURE_COLUMNS


def load_source(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["datetime"])
    df["pig_id"] = df["pig_id"].astype(str)
    return df.sort_values(["pig_id", "datetime"]).reset_index(drop=True)


def resample_to_10min(df: pd.DataFrame, freq: str = RESAMPLE_FREQ) -> pd.DataFrame:
    parts = []
    for pig_id, group in df.groupby("pig_id", dropna=False):
        group = group.sort_values("datetime").set_index("datetime")

        means = group[RAW_FEATURE_COLUMNS].resample(freq).mean()
        means.columns = MEAN_FEATURE_COLUMNS
        stds = group[STD_FEATURES].resample(freq).std()
        stds.columns = STD_FEATURE_COLUMNS
        rows_per_bin = group["condition"].resample(freq).size().rename("source_rows")

        def mode_or_nan(values: pd.Series) -> object:
            modes = values.mode()
            return modes.iloc[0] if len(modes) else np.nan

        condition = group["condition"].resample(freq).agg(mode_or_nan)
        out = pd.concat([means, stds, rows_per_bin, condition], axis=1)
        out["pig_id"] = pig_id
        out = out.dropna(subset=["condition"])
        parts.append(out.reset_index())

    if not parts:
        raise ValueError("No wearable stress biosensor rows remain after resampling.")

    resampled = pd.concat(parts, ignore_index=True)
    resampled[FEATURE_COLUMNS] = resampled.groupby("pig_id")[FEATURE_COLUMNS].transform(
        lambda col: col.interpolate(limit_direction="both")
    )
    resampled[FEATURE_COLUMNS] = resampled[FEATURE_COLUMNS].fillna(0)
    return resampled.sort_values(["pig_id", "datetime"]).reset_index(drop=True)


def split_pair_train_val(
    resampled: pd.DataFrame,
    train_ratio: float,
    seq_len: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts = []
    val_parts = []
    split_rows = []

    pair = resampled[resampled["condition"] == "Pair"].copy()
    for pig_id, group in pair.groupby("pig_id", dropna=False):
        group = group.sort_values("datetime").reset_index(drop=True)
        split_idx = int(len(group) * train_ratio)
        train_group = group.iloc[:split_idx]
        val_group = group.iloc[split_idx:]
        train_windows = max(0, len(train_group) - seq_len + 1)
        val_windows = max(0, len(val_group) - seq_len + 1)
        status = "ok" if train_windows and val_windows else "skipped_no_windows"
        split_rows.append(
            {
                "pig_id": pig_id,
                "pair_rows": len(group),
                "train_rows": len(train_group),
                "val_rows": len(val_group),
                "train_windows": train_windows,
                "val_windows": val_windows,
                "status": status,
            }
        )
        if status == "ok":
            train_parts.append(train_group)
            val_parts.append(val_group)

    if not train_parts or not val_parts:
        raise ValueError("Not enough Pair rows to create train/validation windows.")

    return (
        pd.concat(train_parts, ignore_index=True),
        pd.concat(val_parts, ignore_index=True),
        pd.DataFrame(split_rows),
    )


def _as_chamber_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["dataset_key"] = DATASET_KEY
    out["chamber_number"] = out["pig_id"]
    return out


def fit_transform_global_pair_scaler(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    isolation_df: pd.DataFrame,
    feature_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, StandardScaler]:
    """Fit one Pair scaler and apply it to Pair validation and Isolation rows.

    `pig11` has no Pair rows at all, so a per-animal scaler would leave it
    unscorable. A pooled Pair scaler keeps every animal comparable, the same
    tradeoff already made in `behavior_heat_tolerance.py`.
    """
    feature_columns = feature_columns or FEATURE_COLUMNS
    scaler = StandardScaler()
    scaler.fit(train_df[feature_columns])

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        scaled = df.copy()
        scaled[feature_columns] = scaler.transform(scaled[feature_columns])
        return scaled

    return transform(train_df), transform(val_df), transform(isolation_df), scaler


def build_sequence_metadata(df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
    """One row per window created by `create_sequences`, in the same order.

    `create_sequences` groups by `(dataset_key, chamber_number)`, sorts by
    `datetime`, and slides a `seq_len` window -- this mirrors that exactly so
    row *i* here always describes window *i* of the matching `.npy` array.
    """
    rows = []
    for (dataset_key, chamber_number), group in df.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime").reset_index(drop=True)
        for start in range(len(group) - seq_len + 1):
            end = start + seq_len - 1
            rows.append(
                {
                    "dataset_key": dataset_key,
                    "pig_id": chamber_number,
                    "condition": group.loc[end, "condition"],
                    "start_datetime": group.loc[start, "datetime"],
                    "end_datetime": group.loc[end, "datetime"],
                    "window_start_index": start,
                    "window_end_index": end,
                }
            )
    return pd.DataFrame(rows)


def write_report(
    output_dir: Path,
    source: pd.DataFrame,
    resampled: pd.DataFrame,
    split_summary: pd.DataFrame,
    arrays: dict[str, np.ndarray],
) -> Path:
    condition_counts = resampled.groupby("condition").size().to_frame("rows_10min")
    lines = [
        "# Wearable Stress Biosensor 데이터셋 보고서",
        "",
        f"- source rows: `{len(source)}`",
        f"- resampled 10min rows: `{len(resampled)}`",
        f"- pigs: `{source['pig_id'].nunique()}`",
        f"- feature 수: `{len(FEATURE_COLUMNS)}`",
        f"- X_train shape: `{tuple(arrays['X_train'].shape)}`",
        f"- X_val shape: `{tuple(arrays['X_val'].shape)}`",
        f"- X_test_isolation shape: `{tuple(arrays['X_test_isolation'].shape)}`",
        "",
        "## Feature",
        "",
        ", ".join(f"`{col}`" for col in FEATURE_COLUMNS),
        "",
        "## 조건별 10분 row 수",
        "",
        dataframe_to_markdown(condition_counts),
        "",
        "## Pair train/val split",
        "",
        dataframe_to_markdown(split_summary),
    ]
    report = output_dir / "wearable_stress_biosensor_dataset_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_stress_biosensor_dataset(
    input_path: str | Path = DEFAULT_INPUT,
    processed_output: str | Path = DEFAULT_PROCESSED_OUTPUT,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    seq_len: int = DEFAULT_SEQ_LEN,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
) -> dict[str, np.ndarray]:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    processed_path = Path(processed_output)
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    source = load_source(input_path)
    resampled = resample_to_10min(source)
    resampled.to_csv(processed_path, index=False)
    resampled.to_csv(artifact_path / "wearable_stress_biosensor_timeseries_10min.csv", index=False)

    train_df, val_df, split_summary = split_pair_train_val(resampled, train_ratio=train_ratio, seq_len=seq_len)
    isolation_df = resampled[resampled["condition"] == "Isolation"].copy()

    train_chamber = _as_chamber_frame(train_df)
    val_chamber = _as_chamber_frame(val_df)
    isolation_chamber = _as_chamber_frame(isolation_df)

    train_scaled, val_scaled, isolation_scaled, scaler = fit_transform_global_pair_scaler(
        train_chamber, val_chamber, isolation_chamber
    )

    arrays = {
        "X_train": create_sequences(train_scaled, FEATURE_COLUMNS, seq_len=seq_len),
        "X_val": create_sequences(val_scaled, FEATURE_COLUMNS, seq_len=seq_len),
        "X_test_isolation": create_sequences(isolation_scaled, FEATURE_COLUMNS, seq_len=seq_len),
    }

    for name, array in arrays.items():
        np.save(artifact_path / f"{name}.npy", array)
    pd.Series(FEATURE_COLUMNS, name="feature").to_csv(
        artifact_path / "wearable_stress_biosensor_feature_columns.csv", index=False
    )
    build_sequence_metadata(train_chamber, seq_len).to_csv(
        artifact_path / "wearable_stress_biosensor_train_sequence_metadata.csv", index=False
    )
    build_sequence_metadata(val_chamber, seq_len).to_csv(
        artifact_path / "wearable_stress_biosensor_val_sequence_metadata.csv", index=False
    )
    build_sequence_metadata(isolation_chamber, seq_len).to_csv(
        artifact_path / "wearable_stress_biosensor_isolation_sequence_metadata.csv", index=False
    )
    split_summary.to_csv(artifact_path / "wearable_stress_biosensor_split_summary.csv", index=False)
    joblib.dump(
        {
            "scaler": scaler,
            "feature_columns": FEATURE_COLUMNS,
            "scaling_mode": "global_pair",
            "note": "pig11 has no Pair rows, so a pooled Pair scaler is used instead of per-animal scaling.",
        },
        artifact_path / "wearable_stress_biosensor_scaler.joblib",
    )
    write_report(artifact_path, source, resampled, split_summary, arrays)
    return arrays


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Wearable Stress Biosensor Pair/Isolation sanity-check arrays.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--processed-output", default=DEFAULT_PROCESSED_OUTPUT)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--seq-len", type=int, default=DEFAULT_SEQ_LEN)
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    arrays = build_stress_biosensor_dataset(
        input_path=args.input,
        processed_output=args.processed_output,
        artifact_dir=args.artifact_dir,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
    )
    for name, array in arrays.items():
        print(f"{name} shape:", array.shape)


if __name__ == "__main__":
    main()
