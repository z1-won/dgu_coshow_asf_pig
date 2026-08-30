"""Evaluate Wearable Stress Biosensor Pair/Isolation sanity-check artifacts."""

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


def summarize_by_pig(scored: pd.DataFrame, label: str) -> pd.DataFrame:
    out = (
        scored.groupby("pig_id")
        .agg(
            windows=("confirmed_anomaly", "size"),
            mean_error=("reconstruction_error", "mean"),
            raw_anomaly_rate=("raw_anomaly", "mean"),
            confirmed_anomaly_rate=("confirmed_anomaly", "mean"),
        )
        .reset_index()
    )
    out.insert(0, "split", label)
    return out


def evaluate_stress_biosensor(
    artifact_dir: str | Path = "artifacts/wearable_stress_biosensor_sanity_check",
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
        metadata_name="wearable_stress_biosensor_val_sequence_metadata.csv",
        threshold=threshold,
        consecutive_required=consecutive_required,
    )
    scored_isolation = score_split(
        model,
        artifact_path,
        array_name="X_test_isolation.npy",
        metadata_name="wearable_stress_biosensor_isolation_sequence_metadata.csv",
        threshold=threshold,
        consecutive_required=consecutive_required,
    )

    summary = pd.DataFrame(
        [
            summarize_scored("Pair_validation", scored_val),
            summarize_scored("Isolation_test", scored_isolation),
        ]
    )
    summary["threshold_p99"] = threshold
    summary["threshold_ci_relative_width"] = threshold_ci["ci_relative_width"]

    by_pig = pd.concat(
        [
            summarize_by_pig(scored_val, "Pair_validation"),
            summarize_by_pig(scored_isolation, "Isolation_test"),
        ],
        ignore_index=True,
    )

    return summary, by_pig, pd.concat([scored_val, scored_isolation], ignore_index=True)


def write_report(
    artifact_dir: Path,
    summary: pd.DataFrame,
    by_pig: pd.DataFrame,
    scored: pd.DataFrame,
) -> Path:
    summary.to_csv(artifact_dir / "wearable_stress_biosensor_detection_summary.csv", index=False)
    by_pig.to_csv(artifact_dir / "wearable_stress_biosensor_by_pig_summary.csv", index=False)
    scored.to_csv(artifact_dir / "wearable_stress_biosensor_scored_windows.csv", index=False)

    pair_rate = summary.loc[summary["split"] == "Pair_validation", "confirmed_anomaly_rate"].iloc[0]
    isolation_rate = summary.loc[summary["split"] == "Isolation_test", "confirmed_anomaly_rate"].iloc[0]
    multiplier = isolation_rate / pair_rate if pair_rate else np.inf
    multiplier_text = "무한대" if np.isinf(multiplier) else f"{multiplier:.1f}배"

    report = artifact_dir / "wearable_stress_biosensor_detection_report.md"
    lines = [
        "# Wearable Stress Biosensor 탐지 검증 리포트",
        "",
        "Pair(정상 사육) 구간으로 학습한 LSTM Autoencoder를 Isolation(격리 스트레스) 구간에 적용한 결과입니다.",
        "",
        "## 요약",
        "",
        dataframe_to_markdown(summary),
        "",
        f"- Isolation confirmed anomaly rate는 Pair validation 대비 `{multiplier_text}`입니다.",
        "- `confirmed_anomaly`는 threshold 초과가 같은 돼지(pig_id) 안에서 연속 3개 window 이상 이어진 경우입니다.",
        "- `threshold_ci_relative_width`가 크면 threshold 점추정은 아직 임시 기준으로 봐야 합니다.",
        "",
        "## 돼지별 탐지율",
        "",
        dataframe_to_markdown(by_pig),
        "",
        "## 해석",
        "",
        "- `pig11`은 원본 데이터에 Pair 구간이 없어 validation에 등장하지 않고, "
        "Isolation 결과는 다른 돼지로 학습한 pooled scaler 기준값입니다. "
        "또한 Isolation window가 2개뿐이라 `consecutive_required=3` 조건상 "
        "raw anomaly와 무관하게 confirmed_anomaly는 항상 0이 됩니다 (표본 부족, 모델 실패 아님).",
        "- 이 데이터셋은 ASF 데이터가 아니라 격리 스트레스 데이터입니다. "
        "따라서 결론은 'ASF 탐지 증명'이 아니라 "
        "'정상 사육과 격리 스트레스 상태를 심박/호흡/자세 신호로 구분하는 외부 sanity check 통과 여부'입니다.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Wearable Stress Biosensor Pair/Isolation detection results.")
    parser.add_argument("--artifact-dir", default="artifacts/wearable_stress_biosensor_sanity_check")
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    summary, by_pig, scored = evaluate_stress_biosensor(
        artifact_dir=artifact_dir,
        percentile=args.percentile,
        consecutive_required=args.consecutive_required,
    )
    report = write_report(artifact_dir, summary, by_pig, scored)
    print(f"Wrote {report}")
    print(dataframe_to_markdown(summary[["split", "windows", "confirmed_anomaly_rate"]]))


if __name__ == "__main__":
    main()
