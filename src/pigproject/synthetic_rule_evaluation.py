"""Summarize synthetic rule-event evaluation outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown


DEFAULT_INPUTS = {
    "positive": "artifacts/synthetic_rule_positive_lead_time_summary.csv",
    "negative": "artifacts/synthetic_rule_negative_lead_time_summary.csv",
    "mixed": "artifacts/synthetic_mixed_lead_time_summary.csv",
}


def summarize_file(name: str, path: str | Path) -> tuple[dict, pd.DataFrame]:
    df = pd.read_csv(path, low_memory=False)
    for col in ["caught_within_24h", "caught_within_48h", "caught_within_72h"]:
        df[col] = df[col].astype(bool)
    row = {
        "dataset": name,
        "events": len(df),
        "lead_matched_events": int((df["lead_alert_count"] > 0).sum()),
        "recall_24h": float(df["caught_within_24h"].mean()) if len(df) else 0.0,
        "recall_48h": float(df["caught_within_48h"].mean()) if len(df) else 0.0,
        "recall_72h": float(df["caught_within_72h"].mean()) if len(df) else 0.0,
    }
    by_rule = (
        df.groupby(["event_type", "expected_rule"], dropna=False)
        .agg(
            events=("event_id", "count"),
            matched=("lead_alert_count", lambda s: int((s > 0).sum())),
            recall_24h=("caught_within_24h", "mean"),
            recall_48h=("caught_within_48h", "mean"),
            recall_72h=("caught_within_72h", "mean"),
        )
        .reset_index()
    )
    by_rule.insert(0, "dataset", name)
    return row, by_rule


def build_summary(inputs: dict[str, str | Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    by_rule_frames = []
    for name, path in inputs.items():
        row, by_rule = summarize_file(name, path)
        rows.append(row)
        by_rule_frames.append(by_rule)
    return pd.DataFrame(rows), pd.concat(by_rule_frames, ignore_index=True)


def write_report(summary: pd.DataFrame, by_rule: pd.DataFrame, injection: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Synthetic Rule 검증 결과",
        "",
        "## 파일별 Lead-Time 성능",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Event Type / Expected Rule별 결과",
        "",
        dataframe_to_markdown(by_rule),
        "",
        "## Injection 검증",
        "",
        dataframe_to_markdown(injection),
        "",
        "## 판단",
        "",
        "- positive set이 높게 나오면 현재 경보와 이벤트 매칭/lead-time 평가 로직은 정상이다.",
        "- negative set이 낮게 유지되면 무관한 이벤트를 과하게 맞추지 않는다는 뜻이다.",
        "- injection은 현재 데이터에 실제 hit가 없는 feed/water/ventilation 규칙이 값 변화에는 반응하는지 확인한다.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize synthetic rule-event lead-time evaluations.")
    parser.add_argument("--positive", default=DEFAULT_INPUTS["positive"])
    parser.add_argument("--negative", default=DEFAULT_INPUTS["negative"])
    parser.add_argument("--mixed", default=DEFAULT_INPUTS["mixed"])
    parser.add_argument("--injection", default="artifacts/synthetic_rule_injection_checks.csv")
    parser.add_argument("--summary-output", default="artifacts/synthetic_rule_evaluation_summary.csv")
    parser.add_argument("--by-rule-output", default="artifacts/synthetic_rule_evaluation_by_rule.csv")
    parser.add_argument("--report", default="artifacts/synthetic_rule_evaluation_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary, by_rule = build_summary(
        {
            "positive": args.positive,
            "negative": args.negative,
            "mixed": args.mixed,
        }
    )
    injection = pd.read_csv(args.injection, low_memory=False)

    summary_output = Path(args.summary_output)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_output, index=False)

    by_rule_output = Path(args.by_rule_output)
    by_rule.to_csv(by_rule_output, index=False)
    report = write_report(summary, by_rule, injection, args.report)

    print(f"summary: {summary_output}")
    print(f"by_rule: {by_rule_output}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
