"""Build a ClearFarm-only LSTm Autoencoder baseline (비육돈, model-based, not rule-based).

`clearfarm_rule_validation.py` checks whether existing *rule* thresholds
transfer to ClearFarm. This module builds the project's other detection
layer -- the LSTM Autoencoder -- trained directly on ClearFarm normal pen-day
data, giving the project's first model-based (not threshold-based)
finishing-pig (비육돈) performance number.

Health observations exist for only ~1,038 of 4,147 pen-days (~25%), and on
scattered dates roughly every 3-4 days -- windowing directly on
health-observed rows would leave most pens with too few, non-contiguous
points to form a real sequence. Feed and climate sensors run continuously
regardless, so windows are built on the full daily series per pen (~86 rows
on average) and each window is labeled by its *last* day's health status:
`normal` (health observed, no signs), `symptomatic` (health observed, any
sign present), or `unobserved` (no health check that day). Training uses
only `normal`-ending windows -- `unobserved` is deliberately *not* treated
as normal, unlike the project's AI Hub tracks that have no ground truth at
all -- so this baseline is smaller but methodologically cleaner than
assuming every unlabeled day is fine.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.bioenergy_pipeline import fill_features_with_quality_report
from pigproject.clearfarm_rule_validation import DEFAULT_PEN_DAY_PATH, define_disease_signs, load_pen_day


DEFAULT_ARTIFACT_DIR = "artifacts/clearfarm_baseline"
DEFAULT_SEQ_LEN = 7
DEFAULT_TRAIN_RATIO = 0.8

FEATURE_COLUMNS = [
    "daily_feed_intake_per_pig_kg",
    "mean_visit_duration_sec",
    "mean_feed_rate",
    "active_feeding_pigs",
    "co2_mean",
    "co2_max",
    "ammonia_mean",
    "ammonia_max",
    "humidity_mean",
    "humidity_max",
    "temperature_mean",
    "temperature_max",
]


def load_labeled_pen_day(pen_day_path: str | Path = DEFAULT_PEN_DAY_PATH) -> pd.DataFrame:
    df = load_pen_day(pen_day_path)
    df = define_disease_signs(df)
    observed = df["health_observation_rows"].fillna(0) > 0
    df["day_status"] = np.where(~observed, "unobserved", np.where(df["any_signs"], "symptomatic", "normal"))
    return df


def fit_transform_per_pen_scaler(df: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, dict[str, StandardScaler]]:
    """One scaler per pen, fit on that pen's confirmed-`normal` rows only.

    Fitting on the *full* series (an earlier version of this function did)
    silently folds `symptomatic` days into that pen's own "normal" mean/std,
    which dilutes exactly the deviation the model is supposed to learn to
    flag -- confirmed with real numbers here: reconstruction error on the
    symptomatic test set came out *lower* than on normal validation
    (0.212 vs 0.307 mean) until the scaler was restricted to `normal` rows.
    `unobserved` rows are excluded too, on the same "don't assume unlabeled
    days are normal" principle used elsewhere in this module.
    """
    out = df.copy()
    scalers: dict[str, StandardScaler] = {}
    for pen_id, group in out.groupby("pen_id"):
        normal_rows = group[group["day_status"] == "normal"]
        if len(normal_rows) < 2:
            continue  # no normal baseline for this pen -- leave unscaled, it will also get 0 train windows
        scaler = StandardScaler()
        scaler.fit(normal_rows[feature_columns])
        out.loc[group.index, feature_columns] = scaler.transform(group[feature_columns])
        scalers[pen_id] = scaler
    return out, scalers


def build_sequence_metadata(df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
    rows = []
    for pen_id, group in df.groupby("pen_id", dropna=False):
        group = group.sort_values("date").reset_index(drop=True)
        for start in range(len(group) - seq_len + 1):
            end = start + seq_len - 1
            rows.append(
                {
                    "pen_id": pen_id,
                    "end_date": group.loc[end, "date"],
                    "day_status": group.loc[end, "day_status"],
                    "window_start_index": start,
                    "window_end_index": end,
                }
            )
    return pd.DataFrame(rows)


def create_sequences_for_pen(df: pd.DataFrame, feature_columns: list[str], seq_len: int) -> np.ndarray:
    sequences = []
    for _, group in df.groupby("pen_id", dropna=False):
        group = group.sort_values("date")
        values = group[feature_columns].to_numpy(dtype=np.float32)
        for start in range(len(values) - seq_len + 1):
            sequences.append(values[start : start + seq_len])
    return np.asarray(sequences, dtype=np.float32)


def split_normal_train_val(metadata: pd.DataFrame, train_ratio: float) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Per-pen chronological 80/20 split of `normal`-ending window indices."""
    normal = metadata[metadata["day_status"] == "normal"]
    train_idx, val_idx = [], []
    summary_rows = []
    for pen_id, group in normal.groupby("pen_id"):
        group = group.sort_values("end_date")
        split_at = int(len(group) * train_ratio)
        train_part, val_part = group.iloc[:split_at], group.iloc[split_at:]
        status = "ok" if len(train_part) and len(val_part) else "skipped_no_windows"
        if status == "ok":
            train_idx.extend(train_part.index.tolist())
            val_idx.extend(val_part.index.tolist())
        summary_rows.append(
            {"pen_id": pen_id, "normal_windows": len(group), "train_windows": len(train_part), "val_windows": len(val_part), "status": status}
        )
    return pd.Index(train_idx), pd.Index(val_idx), pd.DataFrame(summary_rows)


def build_clearfarm_baseline_dataset(
    pen_day_path: str | Path = DEFAULT_PEN_DAY_PATH,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    seq_len: int = DEFAULT_SEQ_LEN,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
) -> dict[str, np.ndarray]:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)

    df = load_labeled_pen_day(pen_day_path)
    df, quality_summary = fill_features_with_quality_report(df, FEATURE_COLUMNS)
    quality_summary.to_csv(artifact_path / "clearfarm_baseline_feature_quality.csv", index=False)

    scaled_df, scalers = fit_transform_per_pen_scaler(df, FEATURE_COLUMNS)
    metadata = build_sequence_metadata(scaled_df, seq_len)
    all_sequences = create_sequences_for_pen(scaled_df, FEATURE_COLUMNS, seq_len)
    assert len(metadata) == len(all_sequences)

    train_idx, val_idx, split_summary = split_normal_train_val(metadata, train_ratio)
    test_idx = metadata.index[metadata["day_status"] == "symptomatic"]

    arrays = {"X_train": all_sequences[train_idx], "X_val": all_sequences[val_idx], "X_test_symptomatic": all_sequences[test_idx]}
    for name, array in arrays.items():
        np.save(artifact_path / f"{name}.npy", array)

    metadata.loc[train_idx].to_csv(artifact_path / "clearfarm_baseline_train_sequence_metadata.csv", index=False)
    metadata.loc[val_idx].to_csv(artifact_path / "clearfarm_baseline_val_sequence_metadata.csv", index=False)
    metadata.loc[test_idx].to_csv(artifact_path / "clearfarm_baseline_symptomatic_sequence_metadata.csv", index=False)
    split_summary.to_csv(artifact_path / "clearfarm_baseline_split_summary.csv", index=False)
    pd.Series(FEATURE_COLUMNS, name="feature").to_csv(artifact_path / "clearfarm_baseline_feature_columns.csv", index=False)
    joblib.dump(
        {"scalers": scalers, "feature_columns": FEATURE_COLUMNS, "scaling_mode": "per_pen"},
        artifact_path / "clearfarm_baseline_scalers.joblib",
    )

    lines = [
        "# ClearFarm LSTM Baseline 데이터셋 보고서",
        "",
        f"- 전체 pen-day: `{len(df)}`, pens: `{df['pen_id'].nunique()}`",
        f"- day_status 분포: {df['day_status'].value_counts().to_dict()}",
        f"- window 수: `{len(metadata)}` (seq_len={seq_len})",
        f"- X_train: `{arrays['X_train'].shape}`, X_val: `{arrays['X_val'].shape}`, "
        f"X_test_symptomatic: `{arrays['X_test_symptomatic'].shape}`",
        "",
        "## Feature 결측치 처리",
        "",
        dataframe_to_markdown(quality_summary),
        "",
        "## pen별 정상(normal) window train/val split",
        "",
        dataframe_to_markdown(split_summary),
    ]
    (artifact_path / "clearfarm_baseline_dataset_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return arrays


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ClearFarm LSTM Autoencoder baseline dataset.")
    parser.add_argument("--pen-day-path", default=DEFAULT_PEN_DAY_PATH)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--seq-len", type=int, default=DEFAULT_SEQ_LEN)
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    arrays = build_clearfarm_baseline_dataset(args.pen_day_path, args.artifact_dir, args.seq_len, args.train_ratio)
    for name, array in arrays.items():
        print(f"{name} shape:", array.shape)


if __name__ == "__main__":
    main()
