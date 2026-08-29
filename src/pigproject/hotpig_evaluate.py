"""Evaluate HOTPIG TN/HS sanity-check artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow import keras

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.detect import bootstrap_percentile_ci, detect_anomalies, reconstruction_error


def score_split(
    model: keras.Model,
    artifact_dir: Path,
    array_name: str,
    metadata_name: str,
    threshold: float,
    consecutive_required: int,
) -> pd.DataFrame:
    X = np.load(artifact_dir / array_name)
    metadata = pd.read_csv(artifact_dir / metadata_name)
    errors, raw_flags, confirmed_flags = detect_anomalies(
        model,
        X,
        threshold=threshold,
        consecutive_required=consecutive_required,
        group_ids=metadata["pig_id"].astype(str).to_numpy(),
    )
    metadata = metadata.copy()
    metadata["reconstruction_error"] = errors
    metadata["raw_anomaly"] = raw_flags
    metadata["confirmed_anomaly"] = confirmed_flags
    return metadata


def summarize_scored(label: str, scored: pd.DataFrame) -> dict[str, object]:
    return {
        "split": label,
        "windows": len(scored),
        "mean_error": float(scored["reconstruction_error"].mean()),
        "raw_anomaly_windows": int(scored["raw_anomaly"].sum()),
        "raw_anomaly_rate": float(scored["raw_anomaly"].mean()),
        "confirmed_anomaly_windows": int(scored["confirmed_anomaly"].sum()),
        "confirmed_anomaly_rate": float(scored["confirmed_anomaly"].mean()),
    }


def add_hs_elapsed_day(scored_hs: pd.DataFrame) -> pd.DataFrame:
    out = scored_hs.copy()
    out["end_datetime"] = pd.to_datetime(out["end_datetime"], errors="coerce")
    first_hs_by_pig = out.groupby("pig_id")["end_datetime"].transform("min")
    out["hs_elapsed_day"] = ((out["end_datetime"] - first_hs_by_pig).dt.total_seconds() // 86400 + 1).astype(int)
    return out


def evaluate_hotpig(
    artifact_dir: str | Path = "artifacts/hotpig_sanity_check",
    percentile: float = 99.0,
    consecutive_required: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    artifact_path = Path(artifact_dir)
    model = keras.models.load_model(artifact_path / "best_model.keras")
    X_val = np.load(artifact_path / "X_val.npy")
    val_errors = reconstruction_error(model, X_val)
    threshold = float(np.percentile(val_errors, percentile))
    threshold_ci = bootstrap_percentile_ci(val_errors, percentile=percentile)

    scored_val = score_split(
        model,
        artifact_path,
        array_name="X_val.npy",
        metadata_name="hotpig_val_sequence_metadata.csv",
        threshold=threshold,
        consecutive_required=consecutive_required,
    )
    scored_hs = score_split(
        model,
        artifact_path,
        array_name="X_test_hs.npy",
        metadata_name="hotpig_hs_sequence_metadata.csv",
        threshold=threshold,
        consecutive_required=consecutive_required,
    )
    scored_hs = add_hs_elapsed_day(scored_hs)

    summary = pd.DataFrame(
        [
            summarize_scored("TN_validation", scored_val),
            summarize_scored("HS_test", scored_hs),
        ]
    )
    summary["threshold_p99"] = threshold
    summary["threshold_ci_relative_width"] = threshold_ci["ci_relative_width"]

    hs_by_day = (
        scored_hs.groupby("hs_elapsed_day")
        .agg(
            windows=("confirmed_anomaly", "size"),
            confirmed_anomaly_windows=("confirmed_anomaly", "sum"),
            confirmed_anomaly_rate=("confirmed_anomaly", "mean"),
            mean_error=("reconstruction_error", "mean"),
        )
        .reset_index()
    )
    return summary, hs_by_day, pd.concat([scored_val, scored_hs], ignore_index=True)


def write_report(
    artifact_dir: Path,
    summary: pd.DataFrame,
    hs_by_day: pd.DataFrame,
    scored: pd.DataFrame,
) -> Path:
    summary.to_csv(artifact_dir / "hotpig_detection_summary.csv", index=False)
    hs_by_day.to_csv(artifact_dir / "hotpig_hs_by_day_summary.csv", index=False)
    scored.to_csv(artifact_dir / "hotpig_scored_windows.csv", index=False)

    tn_rate = summary.loc[summary["split"] == "TN_validation", "confirmed_anomaly_rate"].iloc[0]
    hs_rate = summary.loc[summary["split"] == "HS_test", "confirmed_anomaly_rate"].iloc[0]
    multiplier = hs_rate / tn_rate if tn_rate else np.inf
    multiplier_text = "무한대" if np.isinf(multiplier) else f"{multiplier:.1f}배"

    report = artifact_dir / "hotpig_detection_report.md"
    lines = [
        "# HOTPIG 탐지 검증 리포트",
        "",
        "TN 정상 구간으로 학습한 LSTM Autoencoder를 HS 고온스트레스 구간에 적용한 결과입니다.",
        "",
        "## 요약",
        "",
        dataframe_to_markdown(summary),
        "",
        f"- HS confirmed anomaly rate는 TN validation 대비 `{multiplier_text}`입니다.",
        "- `confirmed_anomaly`는 threshold 초과가 연속 3개 window 이상 이어진 경우입니다.",
        "- `threshold_ci_relative_width`가 크면 threshold 점추정은 아직 임시 기준으로 봐야 합니다.",
        "",
        "## HS 경과일별 탐지율",
        "",
        dataframe_to_markdown(hs_by_day),
        "",
        "## 해석",
        "",
        "- HOTPIG는 ASF 데이터가 아니라 고온스트레스 데이터입니다.",
        "- 따라서 결론은 'ASF 탐지 증명'이 아니라 '정상과 물리적 스트레스 상태를 구분하는 외부 sanity check 통과 여부'입니다.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate HOTPIG TN/HS detection results.")
    parser.add_argument("--artifact-dir", default="artifacts/hotpig_sanity_check")
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    summary, hs_by_day, scored = evaluate_hotpig(
        artifact_dir=artifact_dir,
        percentile=args.percentile,
        consecutive_required=args.consecutive_required,
    )
    report = write_report(artifact_dir, summary, hs_by_day, scored)
    print(f"Wrote {report}")
    print(dataframe_to_markdown(summary[["split", "windows", "confirmed_anomaly_rate"]]))


if __name__ == "__main__":
    main()
