"""Build a cleaned normal-baseline bio-energy dataset."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from pigproject.bioenergy_pipeline import (
    ROLLING_FEATURE_SOURCE_COLUMNS,
    aggregate_by_time,
    create_sequences,
    fit_scalers_per_chamber,
    fill_features_with_quality_report,
    read_inputs,
    split_by_group_time,
    transform_per_chamber,
)
from pigproject.rolling_features import add_rolling_features


def normalize_key(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    if text.endswith(".0"):
        text = text[:-2]
    match = re.search(r"(\d{3,})", text)
    if match:
        return match.group(1)
    return text


def collect_excluded_rows(aggregated: pd.DataFrame, detection_table: pd.DataFrame) -> set[int]:
    excluded: set[int] = set()
    confirmed = detection_table["confirmed_anomaly"].astype(str).str.lower().isin({"true", "1", "yes"})
    detections = detection_table[confirmed].copy()
    if detections.empty:
        return excluded

    aggregated = aggregated.copy()
    aggregated["_dataset_key_norm"] = aggregated["dataset_key"].map(normalize_key)
    aggregated["_chamber_number_norm"] = aggregated["chamber_number"].map(normalize_key)
    aggregated["datetime"] = pd.to_datetime(aggregated["datetime"], errors="coerce")

    for _, row in detections.iterrows():
        start = pd.to_datetime(row["start_datetime"], errors="coerce")
        end = pd.to_datetime(row["end_datetime"], errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        mask = (
            (aggregated["_dataset_key_norm"] == normalize_key(row["dataset_key"]))
            & (aggregated["_chamber_number_norm"] == normalize_key(row["chamber_number"]))
            & (aggregated["datetime"] >= start)
            & (aggregated["datetime"] <= end)
        )
        excluded.update(aggregated.index[mask].tolist())
    return excluded


def build_clean_baseline(
    inputs: list[str | Path],
    previous_detection_table: str | Path,
    output_dir: str | Path,
    aggregated_input: str | Path | None = None,
    seq_len: int = 24,
    train_ratio: float = 0.8,
    min_val_windows: int = 10,
    include_features: list[str] | None = None,
    exclude_features: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    if aggregated_input:
        aggregated = pd.read_csv(aggregated_input, low_memory=False)
        aggregated["datetime"] = pd.to_datetime(aggregated["datetime"], errors="coerce")
    else:
        raw = read_inputs(inputs)
        aggregated = aggregate_by_time(raw)
    aggregated = add_rolling_features(aggregated, columns=ROLLING_FEATURE_SOURCE_COLUMNS)
    detection_table = pd.read_csv(previous_detection_table)
    excluded_rows = collect_excluded_rows(aggregated, detection_table)

    clean = aggregated.drop(index=list(excluded_rows)).reset_index(drop=True)
    aggregated.assign(excluded_from_baseline=aggregated.index.isin(excluded_rows)).to_csv(
        output / "bioenergy_baseline_screened_rows.csv",
        index=False,
    )
    clean.to_csv(output / "bioenergy_aggregated.csv", index=False)

    feature_columns = [
        col
        for col in clean.columns
        if col not in {"dataset_key", "chamber_number", "datetime"}
        and clean[col].notna().any()
    ]
    if include_features:
        included = set(include_features)
        feature_columns = [col for col in feature_columns if col in included]
    if exclude_features:
        excluded = set(exclude_features)
        feature_columns = [col for col in feature_columns if col not in excluded]
    if not feature_columns:
        raise ValueError("No feature columns remain after include/exclude filtering.")
    clean, quality_summary = fill_features_with_quality_report(clean, feature_columns)
    quality_summary.to_csv(output / "bioenergy_data_quality_report.csv", index=False)

    train_df, val_df, split_summary = split_by_group_time(
        clean,
        train_ratio=train_ratio,
        seq_len=seq_len,
        min_val_windows=min_val_windows,
    )
    split_summary.to_csv(output / "bioenergy_split_summary.csv", index=False)

    scalers = fit_scalers_per_chamber(train_df, feature_columns)
    joblib.dump(
        {"scalers": scalers, "feature_columns": feature_columns, "scaling_mode": "per_chamber"},
        output / "bioenergy_scaler.joblib",
    )

    train_scaled = transform_per_chamber(train_df, feature_columns, scalers)
    val_scaled = transform_per_chamber(val_df, feature_columns, scalers)

    train_scaled.to_csv(output / "bioenergy_train_scaled.csv", index=False)
    val_scaled.to_csv(output / "bioenergy_val_scaled.csv", index=False)

    X_train = create_sequences(train_scaled, feature_columns, seq_len=seq_len)
    X_val = create_sequences(val_scaled, feature_columns, seq_len=seq_len)
    np.save(output / "X_train.npy", X_train)
    np.save(output / "X_val.npy", X_val)
    pd.Series(feature_columns, name="feature").to_csv(output / "bioenergy_feature_columns.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "source_rows": len(aggregated),
                "excluded_rows": len(excluded_rows),
                "clean_rows": len(clean),
                "confirmed_anomaly_windows_used": int(detection_table["confirmed_anomaly"].sum()),
                "included_features": ",".join(include_features or []),
                "excluded_features": ",".join(exclude_features or []),
                "x_train_shape": str(tuple(X_train.shape)),
                "x_val_shape": str(tuple(X_val.shape)),
            }
        ]
    )
    summary.to_csv(output / "bioenergy_baseline_cleaning_summary.csv", index=False)
    return X_train, X_val, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cleaned normal-baseline arrays from bio-energy CSVs.")
    parser.add_argument("--input", action="append", default=[], help="Input model feature CSV. Repeatable.")
    parser.add_argument("--aggregated-input", default=None, help="Optional prebuilt bioenergy_aggregated.csv.")
    parser.add_argument("--previous-detection-table", required=True)
    parser.add_argument("--output-dir", default="artifacts/bioenergy_baseline")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--min-val-windows", type=int, default=10)
    parser.add_argument("--include-feature", action="append", default=[], help="Feature column to include. Repeatable.")
    parser.add_argument("--exclude-feature", action="append", default=[], help="Feature column to exclude. Repeatable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X_train, X_val, summary = build_clean_baseline(
        inputs=args.input,
        previous_detection_table=args.previous_detection_table,
        output_dir=args.output_dir,
        aggregated_input=args.aggregated_input,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
        min_val_windows=args.min_val_windows,
        include_features=args.include_feature,
        exclude_features=args.exclude_feature,
    )
    print("X_train shape:", X_train.shape)
    print("X_val shape:", X_val.shape)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
