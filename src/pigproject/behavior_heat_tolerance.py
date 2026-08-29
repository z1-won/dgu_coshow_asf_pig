"""Build model-ready Behavior x Heat Tolerance sanity-check data.

The source table records one posture/temperature row every 20 seconds for 22
pigs under TN/HS conditions. This module turns it into the project's standard
10-minute window format, then creates TN train/validation arrays plus an HS
test array for the existing LSTM autoencoder CLIs.
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


POSTURE_VALUES = ["Standing", "Sternal", "Lateral", "Sitting"]
POSTURE_FEATURES = [f"posture_{value.lower()}_ratio" for value in POSTURE_VALUES]
TEMPERATURE_FEATURES = ["muscle_temp_mean", "ambient_temp_mean"]
PERFORMANCE_FEATURES = ["adg_mean", "feed_efficiency_mean"]
BEHAVIOR_FEATURES = POSTURE_FEATURES + ["posture_change_rate"]
FULL_FEATURE_COLUMNS = BEHAVIOR_FEATURES + TEMPERATURE_FEATURES + PERFORMANCE_FEATURES
FEATURE_PROFILES = {
    "behavior_only": BEHAVIOR_FEATURES,
    "behavior_muscle": BEHAVIOR_FEATURES + ["muscle_temp_mean"],
    "full": FULL_FEATURE_COLUMNS,
}
FEATURE_COLUMNS = FULL_FEATURE_COLUMNS
RESAMPLE_FREQ = "10min"


def resolve_feature_columns(feature_profile: str) -> list[str]:
    if feature_profile not in FEATURE_PROFILES:
        valid = ", ".join(sorted(FEATURE_PROFILES))
        raise ValueError(f"Unknown feature profile: {feature_profile}. Choose one of: {valid}.")
    return list(FEATURE_PROFILES[feature_profile])


def load_source(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["datetime", "anim", "condition"]).copy()
    df["anim"] = df["anim"].astype(str)
    for col in ["muscle_temp", "ambient_temp", "adg", "feed_efficiency"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["anim", "datetime"]).reset_index(drop=True)


def resample_to_10min(df: pd.DataFrame, freq: str = RESAMPLE_FREQ) -> pd.DataFrame:
    parts = []
    for anim, group in df.groupby("anim", dropna=False):
        group = group.sort_values("datetime").set_index("datetime")
        posture_dummies = pd.get_dummies(group["posture"])
        for posture in POSTURE_VALUES:
            if posture not in posture_dummies.columns:
                posture_dummies[posture] = 0
        posture_dummies = posture_dummies[POSTURE_VALUES]

        posture_ratio = posture_dummies.resample(freq).mean()
        posture_ratio.columns = POSTURE_FEATURES

        changed = group["posture"].ne(group["posture"].shift()).astype(float)
        posture_change_rate = changed.resample(freq).mean().rename("posture_change_rate")
        numeric = group[["muscle_temp", "ambient_temp", "adg", "feed_efficiency"]].resample(freq).mean()
        numeric = numeric.rename(
            columns={
                "muscle_temp": "muscle_temp_mean",
                "ambient_temp": "ambient_temp_mean",
                "adg": "adg_mean",
                "feed_efficiency": "feed_efficiency_mean",
            }
        )
        rows_per_bin = group["condition"].resample(freq).size().rename("source_rows")

        def mode_or_nan(values: pd.Series) -> object:
            modes = values.mode()
            return modes.iloc[0] if len(modes) else np.nan

        condition = group["condition"].resample(freq).agg(mode_or_nan)
        out = pd.concat([posture_ratio, posture_change_rate, numeric, rows_per_bin, condition], axis=1)
        out = out.rename(columns={"condition": "condition"})
        out["anim"] = anim
        out = out.dropna(subset=["condition"])
        parts.append(out.reset_index())

    if not parts:
        raise ValueError("No behavior heat tolerance rows remain after resampling.")

    resampled = pd.concat(parts, ignore_index=True)
    resampled[FULL_FEATURE_COLUMNS] = resampled[FULL_FEATURE_COLUMNS].interpolate(limit_direction="both")
    resampled[FULL_FEATURE_COLUMNS] = resampled[FULL_FEATURE_COLUMNS].fillna(0)
    return resampled.sort_values(["anim", "datetime"]).reset_index(drop=True)


def split_tn_train_val(
    resampled: pd.DataFrame,
    train_ratio: float,
    seq_len: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts = []
    val_parts = []
    split_rows = []

    tn = resampled[resampled["condition"] == "TN"].copy()
    for anim, group in tn.groupby("anim", dropna=False):
        group = group.sort_values("datetime").reset_index(drop=True)
        split_idx = int(len(group) * train_ratio)
        train_group = group.iloc[:split_idx]
        val_group = group.iloc[split_idx:]
        train_windows = max(0, len(train_group) - seq_len + 1)
        val_windows = max(0, len(val_group) - seq_len + 1)
        status = "ok" if train_windows and val_windows else "skipped_no_windows"
        split_rows.append(
            {
                "anim": anim,
                "tn_rows": len(group),
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
        raise ValueError("Not enough TN rows to create train/validation windows.")

    return (
        pd.concat(train_parts, ignore_index=True),
        pd.concat(val_parts, ignore_index=True),
        pd.DataFrame(split_rows),
    )


def _as_chamber_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["dataset_key"] = "behavior_heat_tolerance"
    out["chamber_number"] = out["anim"]
    return out


def fit_transform_global_tn_scaler(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    hs_df: pd.DataFrame,
    feature_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, StandardScaler]:
    """Fit one TN scaler and apply it to TN validation and HS test rows.

    Unlike HotPig, this dataset is between-subject: most animals appear in
    only one condition. A per-animal scaler would make HS-only animals
    unscorable because no TN baseline exists for that animal, so the honest
    sanity check is a pooled TN scaler.
    """
    feature_columns = feature_columns or FEATURE_COLUMNS
    scaler = StandardScaler()
    scaler.fit(train_df[feature_columns])

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        scaled = df.copy()
        scaled[feature_columns] = scaler.transform(scaled[feature_columns])
        return scaled

    return transform(train_df), transform(val_df), transform(hs_df), scaler


def write_report(
    output_dir: Path,
    source: pd.DataFrame,
    resampled: pd.DataFrame,
    split_summary: pd.DataFrame,
    arrays: dict[str, np.ndarray],
    feature_profile: str,
    feature_columns: list[str],
) -> Path:
    report = output_dir / "behavior_heat_tolerance_dataset_report.md"
    condition_counts = resampled.groupby("condition").size().to_frame("rows_10min")
    posture_counts = source["posture"].value_counts().to_frame("source_rows")
    lines = [
        "# Behavior x Heat Tolerance 데이터셋 보고서",
        "",
        f"- source rows: `{len(source)}`",
        f"- resampled 10min rows: `{len(resampled)}`",
        f"- animals: `{source['anim'].nunique()}`",
        f"- feature 수: `{len(FEATURE_COLUMNS)}`",
        f"- X_train shape: `{tuple(arrays['X_train'].shape)}`",
        f"- X_val shape: `{tuple(arrays['X_val'].shape)}`",
        f"- X_test_hs shape: `{tuple(arrays['X_test_hs'].shape)}`",
        f"- feature profile: `{feature_profile}`",
        "",
        "## Feature",
        "",
        ", ".join(f"`{col}`" for col in feature_columns),
        "",
        "## 조건별 10분 row 수",
        "",
        dataframe_to_markdown(condition_counts),
        "",
        "## 원본 posture 분포",
        "",
        dataframe_to_markdown(posture_counts),
        "",
        "## TN train/val split",
        "",
        dataframe_to_markdown(split_summary),
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_behavior_heat_tolerance_dataset(
    input_path: str | Path,
    processed_output: str | Path,
    artifact_dir: str | Path,
    seq_len: int = 24,
    train_ratio: float = 0.8,
    feature_profile: str = "full",
) -> dict[str, np.ndarray]:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    processed_path = Path(processed_output)
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    feature_columns = resolve_feature_columns(feature_profile)

    source = load_source(input_path)
    resampled = resample_to_10min(source)
    resampled.to_csv(processed_path, index=False)
    resampled.to_csv(artifact_path / "behavior_heat_tolerance_timeseries_10min.csv", index=False)

    train_df, val_df, split_summary = split_tn_train_val(resampled, train_ratio=train_ratio, seq_len=seq_len)
    hs_df = resampled[resampled["condition"] == "HS"].copy()

    train_chamber = _as_chamber_frame(train_df)
    val_chamber = _as_chamber_frame(val_df)
    hs_chamber = _as_chamber_frame(hs_df)

    train_scaled, val_scaled, hs_scaled, scaler = fit_transform_global_tn_scaler(
        train_chamber,
        val_chamber,
        hs_chamber,
        feature_columns=feature_columns,
    )

    arrays = {
        "X_train": create_sequences(train_scaled, feature_columns, seq_len=seq_len),
        "X_val": create_sequences(val_scaled, feature_columns, seq_len=seq_len),
        "X_test_hs": create_sequences(hs_scaled, feature_columns, seq_len=seq_len),
    }

    for name, array in arrays.items():
        np.save(artifact_path / f"{name}.npy", array)
    pd.Series(feature_columns, name="feature").to_csv(
        artifact_path / "behavior_heat_tolerance_feature_columns.csv", index=False
    )
    split_summary.to_csv(artifact_path / "behavior_heat_tolerance_split_summary.csv", index=False)
    joblib.dump(
        {
            "scaler": scaler,
            "feature_columns": feature_columns,
            "feature_profile": feature_profile,
            "scaling_mode": "global_tn",
            "note": "Behavior x Heat Tolerance is between-subject, so HS-only animals use a pooled TN scaler.",
        },
        artifact_path / "behavior_heat_tolerance_scaler.joblib",
    )
    write_report(artifact_path, source, resampled, split_summary, arrays, feature_profile, feature_columns)
    return arrays


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Behavior x Heat Tolerance TN/HS sanity-check arrays.")
    parser.add_argument("--input", default="data/raw/behavior_heat_tolerance/behavior_heat_tolerance.csv")
    parser.add_argument(
        "--processed-output",
        default="data/processed/behavior_heat_tolerance_timeseries_10min.csv",
    )
    parser.add_argument("--artifact-dir", default="artifacts/behavior_heat_tolerance_sanity_check")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument(
        "--feature-profile",
        choices=sorted(FEATURE_PROFILES),
        default="full",
        help="Feature subset to test: behavior_only excludes all temperature/performance values.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    arrays = build_behavior_heat_tolerance_dataset(
        input_path=args.input,
        processed_output=args.processed_output,
        artifact_dir=args.artifact_dir,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
        feature_profile=args.feature_profile,
    )
    for name, array in arrays.items():
        print(f"{name} shape:", array.shape)


if __name__ == "__main__":
    main()
