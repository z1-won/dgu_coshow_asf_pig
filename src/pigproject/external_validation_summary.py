"""Summarize external validation evidence across auxiliary datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return pd.read_csv(path)


def _single_row(df: pd.DataFrame, column: str, value: object) -> pd.Series:
    matches = df[df[column] == value]
    if matches.empty:
        raise ValueError(f"Could not find {column}={value!r}")
    return matches.iloc[0]


def build_external_validation_summary(
    behavior_comparison_path: str | Path,
    hotpig_detection_path: str | Path,
    asf_threshold_sweep_path: str | Path,
    asf_current_threshold: float = 39.5,
) -> pd.DataFrame:
    behavior = _read_csv(Path(behavior_comparison_path))
    hotpig = _read_csv(Path(hotpig_detection_path))
    asf_sweep = _read_csv(Path(asf_threshold_sweep_path))

    behavior_only = _single_row(behavior, "profile", "behavior_only")
    behavior_muscle = _single_row(behavior, "profile", "behavior_muscle")
    behavior_full = _single_row(behavior, "profile", "full")
    tn_validation = _single_row(hotpig, "split", "TN_validation")
    hs_test = _single_row(hotpig, "split", "HS_test")

    asf_current_rows = asf_sweep[np.isclose(asf_sweep["threshold"], asf_current_threshold)]
    if asf_current_rows.empty:
        raise ValueError(f"Could not find ASF threshold {asf_current_threshold}")
    asf_current = asf_current_rows.iloc[0]

    tn_rate = float(tn_validation["confirmed_anomaly_rate"])
    hs_rate = float(hs_test["confirmed_anomaly_rate"])
    hotpig_ratio = hs_rate / tn_rate if tn_rate else np.nan

    rows = [
        {
            "priority": 1,
            "dataset": "HOTPIG",
            "validation_role": "LSTM anomaly pipeline external sanity check",
            "main_result": (
                f"HS confirmed anomaly rate {_pct(hs_rate)} vs TN validation {_pct(tn_rate)} "
                f"({hotpig_ratio:.1f}x)"
            ),
            "project_decision": "Use as evidence that the current anomaly pipeline reacts to physical heat-stress states.",
            "do_not_use_for": "Do not claim ASF detection proof from HOTPIG alone.",
            "next_action": "Keep as recurring regression check when model features or thresholds change.",
        },
        {
            "priority": 2,
            "dataset": "ASF Dryad challenge",
            "validation_role": "ASF rule calibration and clinical-ground-truth evidence",
            "main_result": (
                f"rectal_temp_high {asf_current_threshold:.1f}C: sensitivity {_pct(float(asf_current['sensitivity']))}, "
                f"specificity {_pct(float(asf_current['specificity']))}, precision {_pct(float(asf_current['precision']))}"
            ),
            "project_decision": "Keep rectal_temp_high as a high-precision rule, but combine it with anomaly score and other rules.",
            "do_not_use_for": "Do not use rectal temperature alone as a final ASF diagnosis.",
            "next_action": "Use this result to tune ASF rule-score weighting and alert explanation text.",
        },
        {
            "priority": 3,
            "dataset": "Behavior x Heat Tolerance",
            "validation_role": "Auxiliary physiology/feature-profile check",
            "main_result": (
                f"behavior_only HS confirmed anomaly rate {_pct(float(behavior_only['hs_confirmed_anomaly_rate']))}; "
                f"behavior_muscle {_pct(float(behavior_muscle['hs_confirmed_anomaly_rate']))}; "
                f"full {_pct(float(behavior_full['hs_confirmed_anomaly_rate']))}"
            ),
            "project_decision": "Use as auxiliary evidence only; temperature and muscle-temperature profiles explain the strong separation.",
            "do_not_use_for": "Do not mix directly into the main ASF/activity training set as behavior-only proof.",
            "next_action": "Reference as supporting validation, then prioritize farm-compatible AI Hub/real farm event data.",
        },
    ]
    return pd.DataFrame(rows)


def write_external_validation_report(summary: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "external_validation_summary.csv"
    report_path = output_dir / "external_validation_summary.md"
    summary.to_csv(summary_path, index=False)

    report_lines = [
        "# 외부 검증 데이터 통합 요약",
        "",
        "세 외부 데이터셋은 같은 용도로 섞어 쓰지 않고, 서로 다른 검증 질문에 배치합니다.",
        "",
        "## 우선순위별 판단",
        "",
        dataframe_to_markdown(summary),
        "",
        "## 프로젝트 반영 원칙",
        "",
        "- HOTPIG는 현재 LSTM 이상탐지 파이프라인이 정상 상태와 물리적 스트레스 상태를 구분하는지 확인하는 외부 sanity check입니다.",
        "- ASF Dryad는 ASF 실제 challenge에서 체온 규칙이 어떤 민감도/정밀도를 갖는지 확인하는 규칙 검증 데이터입니다.",
        "- Behavior x Heat Tolerance는 행동 feature만의 강한 증거가 아니라, 근육온도와 환경조건이 포함될 때 열스트레스가 분리된다는 보조 생리 검증입니다.",
        "- 따라서 메인 학습 데이터는 농장/돈방 단위 시계열과 호환되는 데이터로 유지하고, 세 외부 데이터는 검증·설명·규칙 보정에 사용합니다.",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize external validation evidence.")
    parser.add_argument(
        "--behavior-comparison",
        default="artifacts/behavior_heat_tolerance_comparison/behavior_heat_tolerance_profile_comparison.csv",
    )
    parser.add_argument(
        "--hotpig-detection",
        default="artifacts/hotpig_sanity_check/hotpig_detection_summary.csv",
    )
    parser.add_argument(
        "--asf-threshold-sweep",
        default="artifacts/asf_dryad_validation/asf_rectal_temp_threshold_sweep.csv",
    )
    parser.add_argument("--asf-current-threshold", type=float, default=39.5)
    parser.add_argument("--output-dir", default="artifacts/external_validation_summary")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_external_validation_summary(
        behavior_comparison_path=args.behavior_comparison,
        hotpig_detection_path=args.hotpig_detection,
        asf_threshold_sweep_path=args.asf_threshold_sweep,
        asf_current_threshold=args.asf_current_threshold,
    )
    report_path = write_external_validation_report(summary, Path(args.output_dir))
    print(f"Wrote {report_path}")
    print(dataframe_to_markdown(summary[["priority", "dataset", "validation_role", "main_result"]]))


if __name__ == "__main__":
    main()
