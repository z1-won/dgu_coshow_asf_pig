"""Build LSTM-ready sequence arrays from bio-energy label feature CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from pigproject.rolling_features import add_rolling_features

ROLLING_FEATURE_SOURCE_COLUMNS = ["feedstuff_volume_mean", "watersupply_mean"]


BASE_FEATURES = [
    "T",
    "RH",
    "CO2",
    "NH3",
    "breath_rate",
    "distance",
    "weight",
    "rectal_temperature",
    "back_temperature",
    "neck_temperature",
    "head_temperature",
    "ventilation_rate",
    "feedstuff_volume",
    "watersupply",
    "pig_manure",
    "sensible_heat",
    "latent_heat",
]

VARIABILITY_FEATURES = [
    "distance",
    "breath_rate",
    "rectal_temperature",
    "back_temperature",
    "neck_temperature",
    "head_temperature",
]


def read_inputs(paths: list[str | Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        df = pd.read_csv(path, low_memory=False)
        if "dataset_key" not in df.columns:
            df["dataset_key"] = Path(path).stem
        frames.append(df)
    if not frames:
        raise ValueError("At least one input CSV is required.")
    return pd.concat(frames, ignore_index=True)


def aggregate_by_time(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df[df.get("kind", "breathing") == "breathing"]
    df = df.dropna(subset=["dataset_key", "chamber_number", "datetime"])

    for col in BASE_FEATURES:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    group_keys = ["dataset_key", "chamber_number", "datetime"]

    if "pig_number" in df.columns:
        # A chamber+timestamp group pools frames from however many individual pigs
        # happened to be detected right then, and frame counts per pig differ by
        # ~100x (one pig can have 10x+ the detections of another in the same
        # window). Averaging raw frames directly means whichever pig was detected
        # most dominates the "chamber" reading, which shows up as the mean and std
        # swinging between timestamps for no real reason. Average within each pig
        # first, then across pigs, so every individual counts once regardless of
        # how many frames it contributed.
        per_pig = (
            df.groupby(group_keys + ["pig_number"], dropna=False)[BASE_FEATURES].mean().reset_index()
        )
        grouped = per_pig.groupby(group_keys, dropna=False)
        mean_df = grouped[BASE_FEATURES].mean().add_suffix("_mean")
        std_df = grouped[VARIABILITY_FEATURES].std().fillna(0).add_suffix("_std")
        pig_count = df.groupby(group_keys, dropna=False)["pig_number"].nunique().rename("pig_count")
        frame_count = df.groupby(group_keys, dropna=False).size().rename("frame_count")
        out = pd.concat([mean_df, std_df, pig_count, frame_count], axis=1).reset_index()
    else:
        grouped = df.groupby(group_keys, dropna=False)
        mean_df = grouped[BASE_FEATURES].mean().add_suffix("_mean")
        std_df = grouped[VARIABILITY_FEATURES].std().fillna(0).add_suffix("_std")
        count_df = grouped.size().to_frame("frame_count")
        out = pd.concat([mean_df, std_df, count_df], axis=1).reset_index()

    out = out.sort_values(["dataset_key", "chamber_number", "datetime"]).reset_index(drop=True)
    return out


def split_by_group_time(
    df: pd.DataFrame,
    train_ratio: float,
    seq_len: int,
    min_val_windows: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts = []
    val_parts = []
    summary_rows = []
    min_val_len = seq_len + min_val_windows - 1

    for (dataset_key, chamber_number), group in df.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime")
        total_rows = len(group)
        if total_rows < seq_len:
            summary_rows.append(
                {
                    "dataset_key": dataset_key,
                    "chamber_number": chamber_number,
                    "total_rows": total_rows,
                    "train_rows": 0,
                    "val_rows": 0,
                    "train_windows": 0,
                    "val_windows": 0,
                    "overlap_rows": 0,
                    "status": "skipped_too_short",
                }
            )
            continue

        val_len = max(int(np.ceil(total_rows * (1 - train_ratio))), min_val_len)
        val_len = min(total_rows, val_len)

        if total_rows >= seq_len + val_len:
            split_idx = total_rows - val_len
            train_group = group.iloc[:split_idx]
            val_group = group.iloc[split_idx:]
            overlap_rows = 0
            status = "non_overlapping"
        else:
            train_len = max(seq_len, int(np.floor(total_rows * train_ratio)))
            train_len = min(total_rows, train_len)
            train_group = group.iloc[:train_len]
            val_group = group.iloc[-val_len:]
            overlap_rows = max(0, train_group.index.max() - val_group.index.min() + 1)
            status = "overlap_for_short_group"

        train_windows = max(0, len(train_group) - seq_len + 1)
        val_windows = max(0, len(val_group) - seq_len + 1)
        if train_windows == 0 or val_windows == 0:
            status = "skipped_no_windows"
        else:
            train_parts.append(train_group)
            val_parts.append(val_group)

        summary_rows.append(
            {
                "dataset_key": dataset_key,
                "chamber_number": chamber_number,
                "total_rows": total_rows,
                "train_rows": len(train_group),
                "val_rows": len(val_group),
                "train_windows": train_windows,
                "val_windows": val_windows,
                "overlap_rows": overlap_rows,
                "status": status,
            }
        )

    if not train_parts or not val_parts:
        raise ValueError("Not enough grouped timesteps to create train/validation splits.")
    return (
        pd.concat(train_parts, ignore_index=True),
        pd.concat(val_parts, ignore_index=True),
        pd.DataFrame(summary_rows),
    )


def fit_scalers_per_chamber(
    train_df: pd.DataFrame, feature_columns: list[str]
) -> dict[tuple, StandardScaler]:
    """Fit one StandardScaler per (dataset_key, chamber_number) group.

    Chambers differ in baseline sensor/temperature level (different pig
    groups, sensor calibration, barn position), so pooling them into one
    global scaler lets those baseline offsets dominate the model instead of
    real within-chamber deviations. A per-chamber scaler removes each
    chamber's own level/scale before the model ever sees the data.
    """
    scalers: dict[tuple, StandardScaler] = {}
    for (dataset_key, chamber_number), group in train_df.groupby(
        ["dataset_key", "chamber_number"], dropna=False
    ):
        scaler = StandardScaler()
        scaler.fit(group[feature_columns])
        scalers[(dataset_key, chamber_number)] = scaler
    return scalers


def transform_per_chamber(
    df: pd.DataFrame, feature_columns: list[str], scalers: dict[tuple, StandardScaler]
) -> pd.DataFrame:
    scaled = df.copy()
    scaled[feature_columns] = scaled[feature_columns].astype(float)
    for (dataset_key, chamber_number), group in df.groupby(
        ["dataset_key", "chamber_number"], dropna=False
    ):
        key = (dataset_key, chamber_number)
        if key not in scalers:
            raise KeyError(
                f"No scaler fitted for chamber group {key}; it must appear in the training split."
            )
        scaled.loc[group.index, feature_columns] = scalers[key].transform(group[feature_columns])
    return scaled


def create_sequences(df: pd.DataFrame, feature_columns: list[str], seq_len: int) -> np.ndarray:
    sequences = []
    for _, group in df.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime")
        values = group[feature_columns].to_numpy(dtype=np.float32)
        for start in range(len(values) - seq_len + 1):
            sequences.append(values[start : start + seq_len])
    return np.asarray(sequences, dtype=np.float32)


def build_bioenergy_sequences(
    inputs: list[str | Path],
    output_dir: str | Path,
    seq_len: int = 24,
    train_ratio: float = 0.8,
    min_val_windows: int = 10,
    include_features: list[str] | None = None,
    exclude_features: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    raw = read_inputs(inputs)
    aggregated = aggregate_by_time(raw)
    aggregated = add_rolling_features(aggregated, columns=ROLLING_FEATURE_SOURCE_COLUMNS)
    aggregated.to_csv(output / "bioenergy_aggregated.csv", index=False)

    feature_columns = [
        col
        for col in aggregated.columns
        if col not in {"dataset_key", "chamber_number", "datetime"}
        and aggregated[col].notna().any()
    ]
    if include_features:
        included = set(include_features)
        feature_columns = [col for col in feature_columns if col in included]
    if exclude_features:
        excluded = set(exclude_features)
        feature_columns = [col for col in feature_columns if col not in excluded]
    if not feature_columns:
        raise ValueError("No feature columns remain after include/exclude filtering.")
    aggregated[feature_columns] = aggregated[feature_columns].fillna(aggregated[feature_columns].median())
    aggregated[feature_columns] = aggregated[feature_columns].fillna(0)
    train_df, val_df, split_summary = split_by_group_time(
        aggregated,
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
    return X_train, X_val, aggregated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LSTM arrays from bio-energy model feature CSVs.")
    parser.add_argument("--input", action="append", required=True, help="Input model feature CSV. Repeatable.")
    parser.add_argument("--output-dir", default="artifacts/bioenergy")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--min-val-windows", type=int, default=10)
    parser.add_argument("--include-feature", action="append", default=[], help="Feature column to include. Repeatable.")
    parser.add_argument("--exclude-feature", action="append", default=[], help="Feature column to exclude. Repeatable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X_train, X_val, aggregated = build_bioenergy_sequences(
        inputs=args.input,
        output_dir=args.output_dir,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
        min_val_windows=args.min_val_windows,
        include_features=args.include_feature,
        exclude_features=args.exclude_feature,
    )
    print("aggregated rows:", len(aggregated))
    print("X_train shape:", X_train.shape)
    print("X_val shape:", X_val.shape)


if __name__ == "__main__":
    main()
