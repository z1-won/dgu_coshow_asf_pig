"""Run what-if experiments for domain-rule threshold candidates."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.domain_rules import build_window_raw_table, combine_with_model, evaluate_rules, load_rules


DEFAULT_EXPERIMENTS = (
    ("baseline", {}),
    ("co2_1100", {"co2_high": 1100}),
    ("co2_1200", {"co2_high": 1200}),
    ("nh3_12", {"nh3_high": 12}),
    ("nh3_15", {"nh3_high": 15}),
    ("co2_1200_nh3_12", {"co2_high": 1200, "nh3_high": 12}),
    ("co2_1500_nh3_15", {"co2_high": 1500, "nh3_high": 15}),
)


def apply_threshold_overrides(rules: list[dict], overrides: dict[str, float]) -> list[dict]:
    """Return a copied rule list with top-level rule thresholds overridden by id."""
    updated = copy.deepcopy(rules)
    for rule in updated:
        rule_id = str(rule.get("id", ""))
        if rule_id in overrides and "threshold" in rule:
            rule["threshold"] = overrides[rule_id]
    return updated


def summarize_result(name: str, overrides: dict[str, float], result: pd.DataFrame) -> dict[str, object]:
    reason_counts = result[result["final_alert"]]["primary_reason"].value_counts()
    return {
        "experiment": name,
        "overrides": ",".join(f"{rule_id}={value}" for rule_id, value in overrides.items()) or "none",
        "windows": int(len(result)),
        "rule_observation": int(result["rule_observation"].sum()),
        "rule_anomaly": int(result["rule_anomaly"].sum()),
        "final_alert": int(result["final_alert"].sum()),
        "disease_alert": int(result["disease_alert"].sum()),
        "management_alert": int(result["management_alert"].sum()),
        "environment_alert": int(result["environment_alert"].sum()),
        "mean_disease_score": float(result["disease_score"].mean()),
        "max_disease_score": float(result["disease_score"].max()),
        "top_reason": str(reason_counts.index[0]) if len(reason_counts) else "",
        "top_reason_alerts": int(reason_counts.iloc[0]) if len(reason_counts) else 0,
    }


def run_threshold_experiments(
    artifact_dir: str | Path,
    rules_path: str | Path,
    experiments: tuple[tuple[str, dict[str, float]], ...] = DEFAULT_EXPERIMENTS,
    seq_len: int = 24,
) -> dict[str, pd.DataFrame]:
    config = load_rules(rules_path)
    base_rules = config["rules"]
    window_table, _, _ = build_window_raw_table(artifact_dir, seq_len=seq_len)
    detection_windows = pd.read_csv(Path(artifact_dir) / "bioenergy_detection_windows.csv", low_memory=False)

    result_frames = {}
    summary_rows = []
    reason_frames = []
    for name, overrides in experiments:
        rules = apply_threshold_overrides(base_rules, overrides)
        rule_table = evaluate_rules(window_table, rules)
        result = combine_with_model(rule_table, detection_windows)
        result_frames[name] = result
        summary_rows.append(summarize_result(name, overrides, result))
        reason_counts = result[result["final_alert"]]["primary_reason"].value_counts().reset_index()
        reason_counts.columns = ["primary_reason", "alerts"]
        reason_counts.insert(0, "experiment", name)
        reason_frames.append(reason_counts)

    summary = pd.DataFrame(summary_rows)
    baseline = summary[summary["experiment"] == "baseline"].iloc[0]
    for col in ["rule_observation", "rule_anomaly", "final_alert", "disease_alert", "management_alert", "environment_alert"]:
        summary[f"{col}_delta"] = summary[col] - int(baseline[col])
    summary["experiment_recommendation"] = summary.apply(_recommend_experiment, axis=1)
    reason_compare = pd.concat(reason_frames, ignore_index=True) if reason_frames else pd.DataFrame()
    return {
        "summary": summary,
        "reason_compare": reason_compare,
        **{f"result_{name}": frame for name, frame in result_frames.items()},
    }


def _recommend_experiment(row: pd.Series) -> str:
    if row["experiment"] == "baseline":
        return "baseline"
    if int(row["disease_alert_delta"]) < 0:
        return "reject_disease_loss"
    if int(row["environment_alert_delta"]) < 0 and int(row["disease_alert_delta"]) == 0:
        return "candidate_environment_tightening"
    if int(row["final_alert_delta"]) == 0:
        return "no_alert_change"
    return "review_manually"


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for column in ["primary_reason", "top_reason"]:
        if column in display.columns:
            display[column] = display[column].astype(str).str.replace("|", ";", regex=False)
    return display


def write_outputs(results: dict[str, pd.DataFrame], summary_output: str | Path, reason_output: str | Path, report_path: str | Path) -> tuple[Path, Path, Path]:
    summary_path = Path(summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    results["summary"].to_csv(summary_path, index=False)

    reason_path = Path(reason_output)
    reason_path.parent.mkdir(parents=True, exist_ok=True)
    results["reason_compare"].to_csv(reason_path, index=False)

    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Rule Threshold Experiment 리포트",
        "",
        "## 목적",
        "",
        "리뷰 결과에서 오탐 가능성이 높은 rule을 바로 수정하지 않고, 후보 threshold별 경보 변화량을 먼저 비교한다.",
        "",
        "## 실험 요약",
        "",
        dataframe_to_markdown(_display_frame(results["summary"])),
        "",
        "## 경보 이유별 변화",
        "",
        dataframe_to_markdown(_display_frame(results["reason_compare"])) if len(results["reason_compare"]) else "경보 없음.",
        "",
        "## 해석 기준",
        "",
        "- `*_delta`는 baseline 대비 증감이다.",
        "- disease alert가 줄지 않고 environment alert만 줄면 환경 rule 보수화 후보가 된다.",
        "- disease alert까지 같이 줄면 질병 탐지 손실 가능성이 있으므로 보류한다.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path, reason_path, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run domain-rule threshold what-if experiments.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--rules", default="config/domain_rules.json")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--summary-output", default="artifacts/rule_threshold_experiment_summary.csv")
    parser.add_argument("--reason-output", default="artifacts/rule_threshold_experiment_reason_compare.csv")
    parser.add_argument("--report", default="artifacts/rule_threshold_experiment_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_threshold_experiments(args.artifact_dir, args.rules, seq_len=args.seq_len)
    summary, reasons, report = write_outputs(results, args.summary_output, args.reason_output, args.report)
    print(f"summary: {summary}")
    print(f"reason_compare: {reasons}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
