"""Summarize environment weakness improvement evidence across external datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

DEFAULT_CLEARFARM_TEMP_SWEEP = "artifacts/clearfarm_rule_validation/clearfarm_config/clearfarm_barn_temp_high_vs_heat_signs.csv"
DEFAULT_HOTPIG_DETECTION = "artifacts/hotpig_sanity_check/hotpig_detection_summary.csv"
DEFAULT_SOWELL_SUMMARY = "artifacts/external/sowell_lead_time/sowell_lead_time_summary.csv"
DEFAULT_OUTPUT_DIR = "artifacts/environment_weakness_improvement"


def _read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return pd.read_csv(path)


def _pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value * 100:.1f}%"


def choose_clearfarm_candidates(sweep: pd.DataFrame) -> pd.DataFrame:
    required = {"threshold", "sensitivity", "specificity", "precision", "f1", "fp"}
    missing = required - set(sweep.columns)
    if missing:
        raise ValueError(f"ClearFarm sweep missing columns: {sorted(missing)}")
    frame = sweep.copy()
    frame["policy"] = "review"
    frame["selection_reason"] = "threshold candidate"

    best_f1_idx = frame["f1"].idxmax()
    screening_pool = frame[frame["sensitivity"] >= 0.9]
    if screening_pool.empty:
        high_recall_idx = frame.sort_values(["sensitivity", "specificity", "precision"], ascending=False).index[0]
    else:
        high_recall_idx = screening_pool.sort_values(["specificity", "precision", "f1"], ascending=False).index[0]
    high_precision_pool = frame[(frame["precision"] >= 0.45) & (frame["specificity"] >= 0.95)]
    if high_precision_pool.empty:
        high_precision_idx = frame["precision"].idxmax()
    else:
        high_precision_idx = high_precision_pool.sort_values(["f1", "sensitivity"], ascending=False).index[0]

    selections = [
        (best_f1_idx, "balanced", "F1 기준 균형 후보"),
        (high_recall_idx, "screening", "민감도 우선 후보: 놓침을 줄이는 대신 확인 부담 증가"),
        (high_precision_idx, "high_confidence", "정밀도/특이도 우선 후보: 확인 필요 알림용"),
    ]
    rows = []
    for idx, policy, reason in selections:
        row = frame.loc[idx].copy()
        row["policy"] = policy
        row["selection_reason"] = reason
        rows.append(row)
    candidates = pd.DataFrame(rows).drop_duplicates(subset=["policy"])
    return candidates[["policy", "threshold", "sensitivity", "specificity", "precision", "f1", "fp", "selection_reason"]]


def build_environment_evidence(
    clearfarm_temp_sweep_path: str | Path = DEFAULT_CLEARFARM_TEMP_SWEEP,
    hotpig_detection_path: str | Path = DEFAULT_HOTPIG_DETECTION,
    sowell_summary_path: str | Path = DEFAULT_SOWELL_SUMMARY,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    clearfarm = _read_csv(clearfarm_temp_sweep_path)
    hotpig = _read_csv(hotpig_detection_path)
    sowell = _read_csv(sowell_summary_path)

    candidates = choose_clearfarm_candidates(clearfarm)
    tn = hotpig[hotpig["split"].eq("TN_validation")].iloc[0]
    hs = hotpig[hotpig["split"].eq("HS_test")].iloc[0]
    sowell_heat = sowell[sowell["scope"].eq("environment_heat")].iloc[0]
    sowell_cold = sowell[sowell["scope"].eq("environment_cold")].iloc[0]

    hs_rate = float(hs["confirmed_anomaly_rate"])
    tn_rate = float(tn["confirmed_anomaly_rate"])
    evidence = pd.DataFrame(
        [
            {
                "priority": 1,
                "evidence_source": "ClearFarm heat-sign validation",
                "weakness_target": "환경 이상 민감도/정밀도 trade-off",
                "current_best_use": "온도 기준을 단일 확정 알림이 아니라 screening/balanced/high-confidence 3단계로 분리",
                "key_metric": (
                    "balanced threshold "
                    f"{candidates[candidates['policy'].eq('balanced')]['threshold'].iloc[0]:.1f}C: "
                    f"sensitivity {_pct(float(candidates[candidates['policy'].eq('balanced')]['sensitivity'].iloc[0]))}, "
                    f"precision {_pct(float(candidates[candidates['policy'].eq('balanced')]['precision'].iloc[0]))}"
                ),
                "project_decision": "환경 rule은 1개 threshold로 끝내지 않고, 낮은 threshold는 후보 선별, 높은 threshold는 확인 필요 알림에 사용한다.",
            },
            {
                "priority": 2,
                "evidence_source": "SOWELL thermic events",
                "weakness_target": "외부 이벤트에서 환경 센서 반응 검증",
                "current_best_use": "고온/저온 이벤트 중 탐지율을 외부 근거로 사용",
                "key_metric": f"heat during recall {_pct(float(sowell_heat['during_recall']))}; cold during recall {_pct(float(sowell_cold['during_recall']))}",
                "project_decision": "SOWELL은 사전경보 성능이 아니라 이벤트 중 환경 센서 반응 근거로 보고서에 반영한다.",
            },
            {
                "priority": 3,
                "evidence_source": "HotPig LSTM sanity check",
                "weakness_target": "모델이 고온 스트레스 상태에 반응하는지 확인",
                "current_best_use": "환경/행동 feature 변경 시 회귀 테스트",
                "key_metric": f"HS confirmed anomaly rate {_pct(hs_rate)} vs TN {_pct(tn_rate)} ({hs_rate / tn_rate:.1f}x)",
                "project_decision": "LSTM은 고온 상태에 반응하지만, 원인 분리는 rule score와 함께 제시한다.",
            },
        ]
    )
    return candidates, evidence


def write_report(candidates: pd.DataFrame, evidence: pd.DataFrame, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output / "environment_threshold_candidates.csv", index=False)
    evidence.to_csv(output / "environment_external_evidence.csv", index=False)

    cand_display = candidates.copy()
    for col in ["sensitivity", "specificity", "precision", "f1"]:
        cand_display[col] = cand_display[col].map(_pct)
    report = [
        "# 환경 이상 취약점 개선 계획",
        "",
        "## 결론",
        "",
        "현재 추가 데이터로 바로 높일 수 있는 쪽은 전체 조기경보 recall이 아니라 `환경 이상`의 검증 신뢰도다. SOWELL은 고온/저온 이벤트 중 탐지율이 100%라 외부 근거로 강하고, ClearFarm은 threshold별 trade-off를 보여준다.",
        "",
        "## ClearFarm 온도 Threshold 후보",
        "",
        dataframe_to_markdown(cand_display),
        "",
        "## 외부 근거 통합",
        "",
        dataframe_to_markdown(evidence),
        "",
        "## 실행 계획",
        "",
        "1. 대시보드/보고서에는 환경 이상을 `선별`, `확인 필요`, `고확신` 3단계로 분리한다.",
        "2. SOWELL 고온/저온 100% 이벤트 중 탐지율은 환경 rule 설명 근거로만 사용한다.",
        "3. 조기경보 recall 수치 개선은 SOWELL이 아니라 실제 농장 이벤트 로그 또는 자연 발생 질병/설비 이벤트 데이터로 평가한다.",
        "4. 다음 실험은 ClearFarm threshold 28.7C/30.4C/31.6C를 alert policy에 넣고 false alerts/day를 비교한다.",
    ]
    path = output / "environment_weakness_improvement_report.md"
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    return path


def build_environment_weakness_plan(
    clearfarm_temp_sweep_path: str | Path = DEFAULT_CLEARFARM_TEMP_SWEEP,
    hotpig_detection_path: str | Path = DEFAULT_HOTPIG_DETECTION,
    sowell_summary_path: str | Path = DEFAULT_SOWELL_SUMMARY,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    candidates, evidence = build_environment_evidence(clearfarm_temp_sweep_path, hotpig_detection_path, sowell_summary_path)
    report = write_report(candidates, evidence, output_dir)
    return candidates, evidence, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build environment weakness improvement plan from external evidence.")
    parser.add_argument("--clearfarm-temp-sweep", default=DEFAULT_CLEARFARM_TEMP_SWEEP)
    parser.add_argument("--hotpig-detection", default=DEFAULT_HOTPIG_DETECTION)
    parser.add_argument("--sowell-summary", default=DEFAULT_SOWELL_SUMMARY)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates, evidence, report = build_environment_weakness_plan(
        clearfarm_temp_sweep_path=args.clearfarm_temp_sweep,
        hotpig_detection_path=args.hotpig_detection,
        sowell_summary_path=args.sowell_summary,
        output_dir=args.output_dir,
    )
    print(f"report: {report}")
    print(dataframe_to_markdown(candidates))
    print(dataframe_to_markdown(evidence[["priority", "evidence_source", "key_metric"]]))


if __name__ == "__main__":
    main()
