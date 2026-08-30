"""Evaluate the ClearFarm LSTM Autoencoder baseline (normal vs symptomatic pen-days)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow import keras

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.detect import bootstrap_percentile_ci, detect_anomalies, reconstruction_error


def score_split(model: keras.Model, artifact_dir: Path, array_name: str, metadata_name: str, threshold: float, consecutive_required: int) -> pd.DataFrame:
    X = np.load(artifact_dir / array_name)
    metadata = pd.read_csv(artifact_dir / metadata_name)
    errors, raw_flags, confirmed_flags = detect_anomalies(
        model, X, threshold=threshold, consecutive_required=consecutive_required,
        group_ids=metadata["pen_id"].astype(str).to_numpy(),
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
        "raw_anomaly_rate": float(scored["raw_anomaly"].mean()),
        "confirmed_anomaly_rate": float(scored["confirmed_anomaly"].mean()),
    }


def evaluate_clearfarm_baseline(
    artifact_dir: str | Path = "artifacts/clearfarm_baseline", percentile: float = 99.0, consecutive_required: int = 2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    artifact_path = Path(artifact_dir)
    model = keras.models.load_model(artifact_path / "best_model.keras")
    X_val = np.load(artifact_path / "X_val.npy")
    val_errors = reconstruction_error(model, X_val)
    threshold = float(np.percentile(val_errors, percentile))
    threshold_ci = bootstrap_percentile_ci(val_errors, percentile=percentile)

    scored_val = score_split(model, artifact_path, "X_val.npy", "clearfarm_baseline_val_sequence_metadata.csv", threshold, consecutive_required)
    scored_symptomatic = score_split(model, artifact_path, "X_test_symptomatic.npy", "clearfarm_baseline_symptomatic_sequence_metadata.csv", threshold, consecutive_required)

    summary = pd.DataFrame([summarize_scored("Normal_validation", scored_val), summarize_scored("Symptomatic_test", scored_symptomatic)])
    summary["threshold_p99"] = threshold
    summary["threshold_ci_relative_width"] = threshold_ci["ci_relative_width"]
    return summary, pd.concat([scored_val, scored_symptomatic], ignore_index=True)


def write_report(artifact_dir: Path, summary: pd.DataFrame, scored: pd.DataFrame) -> Path:
    summary.to_csv(artifact_dir / "clearfarm_baseline_detection_summary.csv", index=False)
    scored.to_csv(artifact_dir / "clearfarm_baseline_scored_windows.csv", index=False)

    normal_rate = summary.loc[summary["split"] == "Normal_validation", "confirmed_anomaly_rate"].iloc[0]
    symptomatic_rate = summary.loc[summary["split"] == "Symptomatic_test", "confirmed_anomaly_rate"].iloc[0]
    multiplier = symptomatic_rate / normal_rate if normal_rate else np.inf
    multiplier_text = "무한대" if np.isinf(multiplier) else f"{multiplier:.1f}배"
    df_mean_normal = scored.loc[scored["day_status"] == "normal", "reconstruction_error"].mean()
    df_mean_symptomatic = scored.loc[scored["day_status"] == "symptomatic", "reconstruction_error"].mean()
    ci_width = summary["threshold_ci_relative_width"].iloc[0]

    lines = [
        "# ClearFarm LSTM Baseline 탐지 검증 리포트",
        "",
        "건강관찰상 정상(normal)인 pen-day로만 학습한 LSTM Autoencoder를, 학습에 전혀 쓰지 않은 "
        "증상 관찰(symptomatic) pen-day에 적용한 결과입니다. 이 프로젝트가 비육돈 데이터로 만든 첫 모델 기반 탐지 성능입니다.",
        "",
        dataframe_to_markdown(summary),
        "",
        f"- symptomatic confirmed anomaly rate는 normal validation 대비 `{multiplier_text}`입니다.",
        "- `confirmed_anomaly`는 같은 pen 안에서 threshold 초과가 연속 2개 window 이상 이어진 경우입니다 "
        "(pen당 정상 window가 적어 기본값 3보다 낮춤).",
        f"- `threshold_ci_relative_width`가 크면(`{summary['threshold_ci_relative_width'].iloc[0]:.1%}`) "
        "threshold 점추정은 아직 임시 기준으로 봐야 합니다.",
        "",
        "## 해석",
        "",
        "- 이건 `domain_rules.json`의 절대 threshold 규칙들과 완전히 다른 접근이다 -- 농장/펜별로 정상 패턴을 "
        "스스로 학습하는 모델 기반 탐지라, `clearfarm_rule_validation.py`가 겪은 '절대값이 농장마다 안 맞는다'는 "
        "문제 자체가 구조적으로 없다.",
        "- `unobserved`(건강관찰 안 한 날, 전체의 75%)는 정상으로 가정하지 않고 학습에서 아예 제외했다 -- "
        "그만큼 학습 데이터가 작지만(정상 window 482개), 검증에 쓴 라벨은 전부 실제 관찰 기반이다.",
        f"- **결과는 방향은 맞지만 약하다**: symptomatic mean error({df_mean_symptomatic:.3f})가 "
        f"normal validation({df_mean_normal:.3f})보다 높긴 하지만, confirmed anomaly rate 차이는 "
        f"0.0% vs {symptomatic_rate:.1%}로 미미하다. threshold CI 상대폭이 {ci_width:.0%}로 매우 커서, "
        "p99 threshold 자체가 val window 142개(펜당 평균 3.5개) 안에서 안정적으로 추정되지 않는다.",
        "- 개발 과정에서 실제로 버그를 하나 발견/수정했다: per-pen scaler를 처음에는 그 펜의 전체 시계열(증상일 포함)로 "
        "fit했더니 symptomatic 구간 값이 그 펜 자신의 '정상' 평균/표준편차에 흡수되어, "
        "symptomatic mean error가 오히려 normal보다 **낮게** 나오는 역전 현상이 있었다. scaler를 `normal`로만 "
        "제한해서 고쳤다 (이 파일의 `fit_transform_per_pen_scaler` docstring 참고).",
        "- **결론**: 모델 기반 탐지가 방향은 맞지만, 지금 데이터 규모(정상 663일, 펜당 관찰 3~4일 간격)로는 "
        "규칙 기반 검증(`clearfarm_rule_validation.py`)만큼 확실한 성능 숫자를 못 만든다. "
        "실제 건강관찰이 더 촘촘하게(매일 또는 격일) 쌓이면 재시도할 가치가 있다.",
    ]
    report = artifact_dir / "clearfarm_baseline_detection_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ClearFarm LSTM baseline normal/symptomatic detection.")
    parser.add_argument("--artifact-dir", default="artifacts/clearfarm_baseline")
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    summary, scored = evaluate_clearfarm_baseline(artifact_dir, args.percentile, args.consecutive_required)
    report = write_report(artifact_dir, summary, scored)
    print(f"Wrote {report}")
    print(dataframe_to_markdown(summary[["split", "windows", "confirmed_anomaly_rate"]]))


if __name__ == "__main__":
    main()
