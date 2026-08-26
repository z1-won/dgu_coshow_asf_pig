"""Build a sanity-check dataset from the HotPig heat-stress dataset (Zenodo 17090997).

The AI Hub bio-energy data never contains a confirmed real anomaly, so this
whole pipeline has never been checked against a case with known ground truth.
HotPig individually houses 24 pigs and records per-minute behavior/feed data
for 16 days under a controlled schedule: thermo-neutral (TN, 7 days) -> heat
stress (HS, 7 days), with real condition labels. That gives us something the
AI Hub data can't: a genuine "normal" period to train on and a genuine
"abnormal" period to test detection against.

It also has what the AI Hub bio-energy data lacks -- enough history per
individual pig (23,040 minutes each) to window per-pig rather than per-pen
(see docs/CHAMBER_TIMESERIES_LIMITATION.md for why that mattered there).

This intentionally reuses the per-chamber scaler/windowing machinery from
bioenergy_pipeline.py by treating each pig_id as a "chamber" -- same
mechanism, applied where the data density actually supports it. The output
artifact dir is a drop-in target for the existing pig-train/pig-detect CLIs;
no HotPig-specific model or detection code is needed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from pigproject.bioenergy_pipeline import create_sequences, fit_scalers_per_chamber, transform_per_chamber

COUNT_COLUMNS = ["unknown", "standing", "seating", "lying", "eating", "drinking", "cuddling", "curious"]
FLAG_COLUMNS = ["idle", "drink", "eat", "mate"]
RESAMPLE_FREQ = "10min"


def load_pig_series(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={df.columns[0]: "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["pig_id"] = path.stem
    return df


def load_all_pigs(directory: str | Path) -> pd.DataFrame:
    directory = Path(directory)
    paths = sorted(directory.glob("P*.csv"))
    if not paths:
        raise ValueError(f"No P*.csv files found in {directory}")
    return pd.concat([load_pig_series(p) for p in paths], ignore_index=True)


def resample_pig_series(df: pd.DataFrame, freq: str = RESAMPLE_FREQ) -> pd.DataFrame:
    """Resample 1-minute records to `freq` bins, per pig.

    Frame counts (standing/eating/...) are converted to fractions of the
    150-frame minute before averaging; the 0/1 activity flags are averaged
    directly (giving "fraction of minutes in this bin with the flag on");
    feed is summed (total intake in the bin, not an average rate).
    """
    parts = []
    for pig_id, group in df.groupby("pig_id"):
        group = group.set_index("datetime").sort_index()
        for col in COUNT_COLUMNS:
            group[f"{col}_frac"] = group[col] / 150.0
        agg = {f"{col}_frac": "mean" for col in COUNT_COLUMNS}
        agg.update({col: "mean" for col in FLAG_COLUMNS})
        agg["feed"] = "sum"
        resampled = group.resample(freq).agg(agg)
        def _mode_or_nan(s: pd.Series) -> object:
            modes = s.mode()
            return modes.iloc[0] if len(modes) else np.nan

        resampled["conditions"] = group["conditions"].resample(freq).agg(_mode_or_nan)
        resampled["pig_id"] = pig_id
        resampled = resampled.dropna(subset=[f"{COUNT_COLUMNS[0]}_frac"])
        parts.append(resampled.reset_index())
    return pd.concat(parts, ignore_index=True)


def build_sanity_dataset(
    input_dir: str | Path,
    output_dir: str | Path,
    seq_len: int = 24,
    train_ratio: float = 0.8,
) -> dict[str, np.ndarray]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    raw = load_all_pigs(input_dir)
    resampled = resample_pig_series(raw)
    resampled.to_csv(output / "hotpig_resampled.csv", index=False)

    feature_columns = [f"{col}_frac" for col in COUNT_COLUMNS] + FLAG_COLUMNS + ["feed"]

    resampled = resampled.rename(columns={"pig_id": "chamber_number"})
    resampled["dataset_key"] = "hotpig"

    tn = resampled[resampled["conditions"] == "TN"].copy()
    hs = resampled[resampled["conditions"] == "HS"].copy()

    train_parts, val_parts, split_rows = [], [], []
    for pig_id, group in tn.groupby("chamber_number"):
        group = group.sort_values("datetime").reset_index(drop=True)
        split_idx = int(len(group) * train_ratio)
        train_parts.append(group.iloc[:split_idx])
        val_parts.append(group.iloc[split_idx:])
        split_rows.append(
            {
                "pig_id": pig_id,
                "tn_rows": len(group),
                "train_rows": split_idx,
                "val_rows": len(group) - split_idx,
            }
        )
    train_df = pd.concat(train_parts, ignore_index=True)
    val_df = pd.concat(val_parts, ignore_index=True)
    pd.DataFrame(split_rows).to_csv(output / "hotpig_split_summary.csv", index=False)

    scalers = fit_scalers_per_chamber(train_df, feature_columns)
    train_scaled = transform_per_chamber(train_df, feature_columns, scalers)
    val_scaled = transform_per_chamber(val_df, feature_columns, scalers)
    hs_scaled = transform_per_chamber(hs, feature_columns, scalers)

    X_train = create_sequences(train_scaled, feature_columns, seq_len=seq_len)
    X_val = create_sequences(val_scaled, feature_columns, seq_len=seq_len)
    X_hs = create_sequences(hs_scaled, feature_columns, seq_len=seq_len)

    np.save(output / "X_train.npy", X_train)
    np.save(output / "X_val.npy", X_val)
    np.save(output / "X_test_hs.npy", X_hs)
    pd.Series(feature_columns, name="feature").to_csv(output / "hotpig_feature_columns.csv", index=False)
    joblib.dump(
        {"scalers": scalers, "feature_columns": feature_columns, "scaling_mode": "per_pig"},
        output / "hotpig_scaler.joblib",
    )

    return {"X_train": X_train, "X_val": X_val, "X_test_hs": X_hs}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a HotPig TN/HS sanity-check dataset.")
    parser.add_argument("--input-dir", required=True, help="Directory containing HotPig P*.csv files.")
    parser.add_argument("--output-dir", default="artifacts/hotpig_sanity_check")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    arrays = build_sanity_dataset(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
    )
    for name, arr in arrays.items():
        print(f"{name} shape:", arr.shape)


if __name__ == "__main__":
    main()
