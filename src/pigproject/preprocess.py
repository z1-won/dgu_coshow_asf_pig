"""Preprocess normal pig farm data into model-ready sequence arrays."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from pigproject.config import CHAMBER_COL, FEATURE_COLUMNS, TIME_COL
from pigproject.data_io import load_json_records


def build_time_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    parsed = pd.to_datetime(df.get("timestamp"), errors="coerce")

    if {"date", "time"}.issubset(df.columns):
        missing = parsed.isna()
        date_time = df["date"].astype(str).str.strip() + df["time"].astype(str).str.strip()
        parsed.loc[missing] = pd.to_datetime(date_time.loc[missing], format="%y%m%d%H%M", errors="coerce")
        missing = parsed.isna()
        parsed.loc[missing] = pd.to_datetime(date_time.loc[missing], errors="coerce")

    df[TIME_COL] = parsed
    df = df.dropna(subset=[CHAMBER_COL, TIME_COL])
    return df.sort_values([CHAMBER_COL, TIME_COL]).reset_index(drop=True)


def coerce_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    return df


def resample_per_chamber(df: pd.DataFrame, freq: str = "10min") -> pd.DataFrame:
    df = coerce_features(df)
    parts = []
    for chamber, group in df.groupby(CHAMBER_COL):
        resampled = group.set_index(TIME_COL)[FEATURE_COLUMNS].resample(freq).mean()
        resampled = resampled.interpolate(limit_direction="both")
        resampled[CHAMBER_COL] = chamber
        parts.append(resampled.reset_index())

    if not parts:
        raise ValueError("No chamber data remains after timestamp parsing.")
    return pd.concat(parts, ignore_index=True)


def split_by_chamber_time(df: pd.DataFrame, train_ratio: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_parts = []
    val_parts = []
    for _, group in df.groupby(CHAMBER_COL):
        group = group.sort_values(TIME_COL)
        split_idx = int(len(group) * train_ratio)
        train_parts.append(group.iloc[:split_idx])
        val_parts.append(group.iloc[split_idx:])
    return pd.concat(train_parts), pd.concat(val_parts)


def create_sequences(df: pd.DataFrame, seq_len: int = 144) -> np.ndarray:
    sequences = []
    for _, group in df.groupby(CHAMBER_COL):
        values = group.sort_values(TIME_COL)[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
        for start in range(len(values) - seq_len + 1):
            sequences.append(values[start : start + seq_len])
    return np.asarray(sequences, dtype=np.float32)


def fit_transform_save(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scaler = StandardScaler()
    scaler.fit(train_df[FEATURE_COLUMNS])
    joblib.dump(scaler, output_dir / "scaler.joblib")

    train_scaled = train_df.copy()
    val_scaled = val_df.copy()
    train_scaled[FEATURE_COLUMNS] = scaler.transform(train_scaled[FEATURE_COLUMNS])
    val_scaled[FEATURE_COLUMNS] = scaler.transform(val_scaled[FEATURE_COLUMNS])
    return train_scaled, val_scaled


def preprocess_json(
    json_dir: str | Path,
    output_dir: str | Path,
    freq: str = "10min",
    seq_len: int = 144,
    train_ratio: float = 0.8,
    max_files: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    raw = load_json_records(json_dir, max_files=max_files)
    indexed = build_time_index(raw)
    resampled = resample_per_chamber(indexed, freq=freq)
    train_df, val_df = split_by_chamber_time(resampled, train_ratio=train_ratio)
    train_scaled, val_scaled = fit_transform_save(train_df, val_df, output)

    X_train = create_sequences(train_scaled, seq_len=seq_len)
    X_val = create_sequences(val_scaled, seq_len=seq_len)

    np.save(output / "X_train.npy", X_train)
    np.save(output / "X_val.npy", X_val)
    train_scaled.to_csv(output / "train_resampled.csv", index=False)
    val_scaled.to_csv(output / "val_resampled.csv", index=False)
    return X_train, X_val


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess AI Hub pig farm JSON data.")
    parser.add_argument("--json-dir", required=True)
    parser.add_argument("--output-dir", default="artifacts")
    parser.add_argument("--freq", default="10min")
    parser.add_argument("--seq-len", type=int, default=144)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--max-files", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X_train, X_val = preprocess_json(
        json_dir=args.json_dir,
        output_dir=args.output_dir,
        freq=args.freq,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
        max_files=args.max_files,
    )
    print("X_train shape:", X_train.shape)
    print("X_val shape:", X_val.shape)


if __name__ == "__main__":
    main()
