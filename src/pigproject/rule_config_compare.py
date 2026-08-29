"""Compare two domain-rule config files on the same bioenergy artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.domain_rules import build_window_raw_table, combine_with_model, evaluate_rules, load_rules
from pigproject.rule_threshold_experiment import _display_frame, summarize_result


def evaluate_config(artifact_dir: str | Path, rules_path: str | Path, seq_len: int = 24) -> pd.DataFrame:
    window_table, _, _ = build_window_raw_table(artifact_dir, seq_len=seq_len)
    detection_windows = pd.read_csv(Path(artifact_dir) / "bioenergy_detection_windows.csv", low_memory=False)
    rules = load_rules(rules_path)["rules"]
    return combine_with_model(evaluate_rules(window_table, rules), detection_windows)


def compare_configs(
    artifact_dir: str | Path,
    baseline_rules: str | Path,
    candidate_rules: str | Path,
    seq_len: int = 24,
) -> dict[str, pd.DataFrame]:
    baseline = evaluate_config(artifact_dir, baseline_rules, seq_len=seq_len)
    candidate = evaluate_config(artifact_dir, candidate_rules, seq_len=seq_len)
    summary = pd.DataFrame(
        [
            summarize_result("baseline_config", {}, baseline),
            summarize_result("candidate_config", {}, candidate),
        ]
    )
    base = summary[summary["experiment"] == "baseline_config"].iloc[0]
    for col in ["rule_observation", "rule_anomaly", "final_alert", "disease_alert", "management_alert", "environment_alert"]:
        summary[f"{col}_delta"] = summary[col] - int(base[col])

    reason_compare = pd.concat(
        [
            baseline[baseline["final_alert"]]["primary_reason"].value_counts().rename("baseline_alerts"),
            candidate[candidate["final_alert"]]["primary_reason"].value_counts().rename("candidate_alerts"),
        ],
        axis=1,
    ).fillna(0).astype(int).reset_index(names="primary_reason")
    reason_compare["alert_delta"] = reason_compare["candidate_alerts"] - reason_compare["baseline_alerts"]
    return {"summary": summary, "reason_compare": reason_compare, "baseline": baseline, "candidate": candidate}


def write_report(results: dict[str, pd.DataFrame], summary_output: str | Path, reason_output: str | Path, report_path: str | Path) -> tuple[Path, Path, Path]:
    summary_path = Path(summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    results["summary"].to_csv(summary_path, index=False)

    reason_path = Path(reason_output)
    reason_path.parent.mkdir(parents=True, exist_ok=True)
    results["reason_compare"].to_csv(reason_path, index=False)

    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Rule Config Compare 리포트",
        "",
        "## 요약",
        "",
        dataframe_to_markdown(_display_frame(results["summary"])),
        "",
        "## 경보 이유별 차이",
        "",
        dataframe_to_markdown(_display_frame(results["reason_compare"])) if len(results["reason_compare"]) else "경보 없음.",
        "",
        "## 판단 기준",
        "",
        "- candidate에서 disease alert가 유지되고 environment alert만 줄면 후보 config는 실험 적용 가능하다.",
        "- 실제 운영 config 반영 전에는 incident review log의 confirmed/false_alarm 근거를 함께 확인한다.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path, reason_path, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate domain-rule configs.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--baseline-rules", default="config/domain_rules.json")
    parser.add_argument("--candidate-rules", default="config/domain_rules_candidate_co2_1100.json")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--summary-output", default="artifacts/rule_candidate_config_compare_summary.csv")
    parser.add_argument("--reason-output", default="artifacts/rule_candidate_config_compare_reason.csv")
    parser.add_argument("--report", default="artifacts/rule_candidate_config_compare_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = compare_configs(args.artifact_dir, args.baseline_rules, args.candidate_rules, seq_len=args.seq_len)
    summary, reason, report = write_report(results, args.summary_output, args.reason_output, args.report)
    print(f"summary: {summary}")
    print(f"reason_compare: {reason}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
