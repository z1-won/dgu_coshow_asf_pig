"""Compare ClearFarm environment alert policies at candidate temperature thresholds."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.clearfarm_rule_validation import confusion_for_threshold

DEFAULT_SCORED_PATH = "artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_scored_pen_days.csv"
DEFAULT_CANDIDATES_PATH = "artifacts/environment_weakness_improvement/environment_threshold_candidates.csv"
DEFAULT_OUTPUT_DIR = "artifacts/clearfarm_environment_policy_experiment"

POLICY_LABELS = {
    "screening": "선별",
    "balanced": "균형",
    "high_confidence": "고확신",
}


def _read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return pd.read_csv(path)


def _pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value * 100:.1f}%"


def build_policy_comparison(scored: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    required_scored = {"temperature_max", "heat_signs", "date", "pen_id"}
    required_candidates = {"policy", "threshold"}
    missing_scored = required_scored - set(scored.columns)
    missing_candidates = required_candidates - set(candidates.columns)
    if missing_scored:
        raise ValueError(f"scored data missing columns: {sorted(missing_scored)}")
    if missing_candidates:
        raise ValueError(f"candidate data missing columns: {sorted(missing_candidates)}")

    frame = scored.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    total_pen_days = len(frame.dropna(subset=["temperature_max", "heat_signs"]))
    observed_days = frame["date"].nunique()
    rows = []
    for _, candidate in candidates.sort_values("threshold").iterrows():
        policy = str(candidate["policy"])
        threshold = float(candidate["threshold"])
        metrics = confusion_for_threshold(frame, "temperature_max", threshold, "heat_signs", direction="above")
        alerts = frame[frame["temperature_max"] >= threshold].copy()
        false_alerts = alerts[~alerts["heat_signs"].fillna(False).astype(bool)]
        true_alerts = alerts[alerts["heat_signs"].fillna(False).astype(bool)]
        rows.append(
            {
                "policy": policy,
                "policy_label": POLICY_LABELS.get(policy, policy),
                "threshold_c": threshold,
                "n": int(metrics["n"]),
                "alerts": int(metrics["tp"] + metrics["fp"]),
                "tp": int(metrics["tp"]),
                "fn": int(metrics["fn"]),
                "fp": int(metrics["fp"]),
                "tn": int(metrics["tn"]),
                "recall": float(metrics["sensitivity"]),
                "specificity": float(metrics["specificity"]),
                "precision": float(metrics["precision"]),
                "f1": float(metrics["f1"]),
                "alert_pen_day_rate": (metrics["tp"] + metrics["fp"]) / total_pen_days if total_pen_days else np.nan,
                "false_alerts_per_observed_day": len(false_alerts) / observed_days if observed_days else np.nan,
                "false_alerts_per_100_pen_days": len(false_alerts) / total_pen_days * 100 if total_pen_days else np.nan,
                "true_alert_dates": int(true_alerts["date"].nunique()),
                "false_alert_dates": int(false_alerts["date"].nunique()),
                "decision": _decision_text(policy, threshold, metrics),
            }
        )
    order = {"screening": 1, "balanced": 2, "high_confidence": 3}
    out = pd.DataFrame(rows)
    out["policy_order"] = out["policy"].map(order).fillna(99)
    return out.sort_values(["policy_order", "threshold_c"]).drop(columns=["policy_order"]).reset_index(drop=True)


def _decision_text(policy: str, threshold: float, metrics: dict[str, float]) -> str:
    if policy == "screening":
        return "놓침을 줄이는 1차 선별. 단독 알림보다 관찰/추세 확인에 적합."
    if policy == "balanced":
        return "F1 균형 후보. 환경 이상 기본 운영 기준으로 가장 현실적."
    if policy == "high_confidence":
        return "오탐을 줄인 고확신 기준. CCTV/현장 확인 우선순위에 적합."
    return f"{threshold:.1f}C 후보 기준."


def build_daily_alert_examples(scored: pd.DataFrame, candidates: pd.DataFrame, max_rows_per_policy: int = 20) -> pd.DataFrame:
    frame = scored.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    rows = []
    show_cols = [
        "policy",
        "policy_label",
        "threshold_c",
        "experiment",
        "pen_id",
        "date",
        "temperature_max",
        "heat_signs",
        "any_signs",
        "rule_reasons",
        "rule_score",
        "environment_score",
    ]
    for _, candidate in candidates.iterrows():
        policy = str(candidate["policy"])
        threshold = float(candidate["threshold"])
        alerts = frame[frame["temperature_max"] >= threshold].copy()
        if alerts.empty:
            continue
        alerts["policy"] = policy
        alerts["policy_label"] = POLICY_LABELS.get(policy, policy)
        alerts["threshold_c"] = threshold
        alerts = alerts.sort_values(["heat_signs", "temperature_max"], ascending=[False, False]).head(max_rows_per_policy)
        rows.append(alerts[[c for c in show_cols if c in alerts.columns]])
    if not rows:
        return pd.DataFrame(columns=show_cols)
    return pd.concat(rows, ignore_index=True)


def _format(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["recall", "specificity", "precision", "f1", "alert_pen_day_rate"]:
        if col in out:
            out[col] = out[col].map(_pct)
    for col in ["threshold_c", "false_alerts_per_observed_day", "false_alerts_per_100_pen_days", "temperature_max", "rule_score", "environment_score"]:
        if col in out:
            out[col] = out[col].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    return out


def write_outputs(comparison: pd.DataFrame, examples: pd.DataFrame, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output / "clearfarm_environment_policy_comparison.csv", index=False)
    examples.to_csv(output / "clearfarm_environment_policy_alert_examples.csv", index=False)

    lines = [
        "# ClearFarm 환경 Threshold 3단계 비교 실험",
        "",
        "## 결론",
        "",
        "온도 기준을 하나로 고정하지 않고 `선별`, `균형`, `고확신`으로 분리하면 운영 목적별로 수치를 다르게 쓸 수 있다. 선별 기준은 recall을 높이지만 false alert 부담이 커지고, 고확신 기준은 false alert를 줄이지만 놓치는 이벤트가 많다.",
        "",
        "## 정책별 수치",
        "",
        dataframe_to_markdown(_format(comparison)),
        "",
        "## 알림 예시",
        "",
        dataframe_to_markdown(_format(examples.head(60))) if len(examples) else "해당 없음.",
        "",
        "## 프로젝트 반영 판단",
        "",
        "- 운영 UI에서는 `선별`을 즉시 출동 알림으로 쓰지 말고 관찰/추세 확인 단계로 표시한다.",
        "- `균형`은 환경 이상 기본 기준 후보로 쓸 수 있다.",
        "- `고확신`은 CCTV/현장 확인 우선순위로 쓸 수 있다.",
        "- 다음 단계에서는 이 비교표를 대시보드 성능 페이지에 추가하되, 현장 운영자 화면에는 과도한 성능 용어를 노출하지 않는다.",
    ]
    report = output / "clearfarm_environment_policy_experiment_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_experiment(
    scored_path: str | Path = DEFAULT_SCORED_PATH,
    candidates_path: str | Path = DEFAULT_CANDIDATES_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    scored = _read_csv(scored_path)
    candidates = _read_csv(candidates_path)
    comparison = build_policy_comparison(scored, candidates)
    examples = build_daily_alert_examples(scored, candidates)
    report = write_outputs(comparison, examples, output_dir)
    return comparison, examples, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare ClearFarm 3-level environment temperature policies.")
    parser.add_argument("--scored-path", default=DEFAULT_SCORED_PATH)
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison, _, report = run_experiment(args.scored_path, args.candidates, args.output_dir)
    print(f"report: {report}")
    print(dataframe_to_markdown(_format(comparison)))


if __name__ == "__main__":
    main()
