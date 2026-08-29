"""Compare Behavior x Heat Tolerance feature-profile sanity checks."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow import keras

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.detect import bootstrap_percentile_ci, detect_anomalies, reconstruction_error


DEFAULT_PROFILES = ["behavior_only", "behavior_muscle", "full"]


def summarize_profile(
    profile: str,
    artifact_dir: Path,
    percentile: float,
    consecutive_required: int,
) -> dict[str, object]:
    model = keras.models.load_model(artifact_dir / "best_model.keras")
    X_val = np.load(artifact_dir / "X_val.npy")
    X_hs = np.load(artifact_dir / "X_test_hs.npy")
    features = pd.read_csv(artifact_dir / "behavior_heat_tolerance_feature_columns.csv")["feature"].tolist()

    val_errors = reconstruction_error(model, X_val)
    threshold = float(np.percentile(val_errors, percentile))
    ci = bootstrap_percentile_ci(val_errors, percentile=percentile)

    hs_errors, hs_raw, hs_confirmed = detect_anomalies(
        model,
        X_hs,
        threshold=threshold,
        consecutive_required=consecutive_required,
    )
    val_errors_scored, val_raw, val_confirmed = detect_anomalies(
        model,
        X_val,
        threshold=threshold,
        consecutive_required=consecutive_required,
    )

    return {
        "profile": profile,
        "feature_count": len(features),
        "features": ", ".join(features),
        "val_windows": len(X_val),
        "hs_windows": len(X_hs),
        "threshold_p99": threshold,
        "threshold_ci_relative_width": ci["ci_relative_width"],
        "val_mean_error": float(val_errors_scored.mean()),
        "val_raw_anomaly_rate": float(val_raw.mean()),
        "val_confirmed_anomaly_rate": float(val_confirmed.mean()),
        "hs_mean_error": float(hs_errors.mean()),
        "hs_raw_anomaly_rate": float(hs_raw.mean()),
        "hs_confirmed_anomaly_rate": float(hs_confirmed.mean()),
    }


def compare_profiles(
    artifact_root: str | Path = "artifacts",
    profiles: list[str] | None = None,
    percentile: float = 99.0,
    consecutive_required: int = 3,
) -> pd.DataFrame:
    root = Path(artifact_root)
    rows = []
    for profile in profiles or DEFAULT_PROFILES:
        rows.append(
            summarize_profile(
                profile=profile,
                artifact_dir=root / f"behavior_heat_tolerance_{profile}",
                percentile=percentile,
                consecutive_required=consecutive_required,
            )
        )
    return pd.DataFrame(rows)


def write_report(summary: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "behavior_heat_tolerance_profile_comparison.csv"
    report_path = output_dir / "behavior_heat_tolerance_profile_comparison.md"
    summary.to_csv(summary_path, index=False)

    display_cols = [
        "profile",
        "feature_count",
        "val_windows",
        "hs_windows",
        "threshold_p99",
        "threshold_ci_relative_width",
        "val_confirmed_anomaly_rate",
        "hs_confirmed_anomaly_rate",
    ]
    report_lines = [
        "# Behavior x Heat Tolerance 프로파일 비교",
        "",
        "TN 정상군으로 학습하고, TN validation 기준 p99 threshold를 잡은 뒤 HS 구간을 탐지한 결과입니다.",
        "",
        "## 요약",
        "",
        dataframe_to_markdown(summary[display_cols]),
        "",
        "## 해석 기준",
        "",
        "- `behavior_only`: 자세 비율과 자세 변화율만 사용합니다. 온도값 없이 행동 변화만 보는 검증입니다.",
        "- `behavior_muscle`: 행동 feature에 근육온도만 추가합니다. 환경온도를 직접 보지는 않습니다.",
        "- `full`: 행동, 근육온도, 환경온도, 성장/사료효율 값을 모두 사용합니다.",
        "",
        "## Feature 목록",
        "",
        dataframe_to_markdown(summary[["profile", "features"]]),
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Behavior x Heat Tolerance feature profiles.")
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--output-dir", default="artifacts/behavior_heat_tolerance_comparison")
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = compare_profiles(
        artifact_root=args.artifact_root,
        percentile=args.percentile,
        consecutive_required=args.consecutive_required,
    )
    report = write_report(summary, Path(args.output_dir))
    print(f"Wrote {report}")
    print(dataframe_to_markdown(summary[["profile", "feature_count", "hs_confirmed_anomaly_rate"]]))


if __name__ == "__main__":
    main()
