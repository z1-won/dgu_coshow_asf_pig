"""Build a filled incident-review example and derived tuning reports."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.incident_review import (
    REVIEW_STATUS_CONFIRMED,
    REVIEW_STATUS_FALSE_ALARM,
    REVIEW_STATUS_NEEDS_DATA,
    REVIEW_STATUS_PENDING,
    summarize_review_log,
    write_report as write_review_report,
    write_review_log,
)
from pigproject.rule_tuning_recommendation import build_rule_feedback, load_rule_config, write_outputs


def build_sample_review_log(review_template: pd.DataFrame) -> pd.DataFrame:
    """Fill a deterministic example review log for demonstration."""
    review_log = review_template.copy()
    text_columns = [
        "review_status",
        "actual_cause",
        "resolved_at",
        "operator_note",
        "reviewed_by",
        "reviewed_at",
        "followup_action",
    ]
    for column in text_columns:
        if column in review_log.columns:
            review_log[column] = review_log[column].fillna("").astype(object)
    for column in ["confirmed", "false_alarm", "followup_required"]:
        if column in review_log.columns:
            review_log[column] = review_log[column].astype(object)

    for idx, row in review_log.iterrows():
        queue = str(row.get("queue", ""))
        reason = str(row.get("reason", ""))
        review_log.at[idx, "reviewed_by"] = "sample_operator"
        review_log.at[idx, "reviewed_at"] = "2026-08-30 09:00:00"
        review_log.at[idx, "resolved_at"] = row.get("incident_end_datetime", "")

        if queue == "disease":
            review_log.at[idx, "review_status"] = REVIEW_STATUS_CONFIRMED
            review_log.at[idx, "confirmed"] = True
            review_log.at[idx, "false_alarm"] = False
            review_log.at[idx, "actual_cause"] = "fever"
            review_log.at[idx, "operator_note"] = "샘플 시나리오: 체온 상승 경보를 실제 이상으로 확인"
            review_log.at[idx, "followup_required"] = True
            review_log.at[idx, "followup_action"] = "수의사 확인 및 격리 판단"
        elif queue == "environment" and ("co2_high" in reason or "nh3_high" in reason):
            review_log.at[idx, "review_status"] = REVIEW_STATUS_FALSE_ALARM
            review_log.at[idx, "confirmed"] = False
            review_log.at[idx, "false_alarm"] = True
            review_log.at[idx, "actual_cause"] = "sensor_error"
            review_log.at[idx, "operator_note"] = "샘플 시나리오: 센서 보정 문제로 판단"
            review_log.at[idx, "followup_required"] = True
            review_log.at[idx, "followup_action"] = "CO2/NH3 센서 보정 및 환기 로그 대조"
        elif queue == "management":
            review_log.at[idx, "review_status"] = REVIEW_STATUS_CONFIRMED
            review_log.at[idx, "confirmed"] = True
            review_log.at[idx, "false_alarm"] = False
            review_log.at[idx, "actual_cause"] = "feed_or_water_supply_issue"
            review_log.at[idx, "operator_note"] = "샘플 시나리오: 급이/급수 계열 확인 필요"
            review_log.at[idx, "followup_required"] = True
            review_log.at[idx, "followup_action"] = "급이/급수 라인 점검"
        else:
            review_log.at[idx, "review_status"] = REVIEW_STATUS_NEEDS_DATA
            review_log.at[idx, "confirmed"] = False
            review_log.at[idx, "false_alarm"] = False
            review_log.at[idx, "actual_cause"] = ""
            review_log.at[idx, "operator_note"] = "샘플 시나리오: 추가 데이터 필요"
            review_log.at[idx, "followup_required"] = True
            review_log.at[idx, "followup_action"] = "원자료와 현장 로그 추가 확인"

    review_log["review_status"] = review_log["review_status"].fillna(REVIEW_STATUS_PENDING)
    return review_log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a sample filled incident review and tuning report.")
    parser.add_argument("--review-template", default="data/templates/incident_review_log_template.csv")
    parser.add_argument("--rules-config", default="config/domain_rules.json")
    parser.add_argument("--output-review-log", default="data/templates/sample_incident_review_log.csv")
    parser.add_argument("--summary-output", default="artifacts/sample_incident_review_summary.csv")
    parser.add_argument("--review-report", default="artifacts/sample_incident_review_report.md")
    parser.add_argument("--recommendations-output", default="artifacts/sample_rule_tuning_recommendations.csv")
    parser.add_argument("--recommendations-report", default="artifacts/sample_rule_tuning_recommendations_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review_template = pd.read_csv(args.review_template, low_memory=False)
    review_log = build_sample_review_log(review_template)
    summary = summarize_review_log(review_log)
    rule_config = load_rule_config(args.rules_config)
    recommendations = build_rule_feedback(review_log, rule_config)

    review_path = write_review_log(review_log, args.output_review_log)
    summary_path = write_review_log(summary, args.summary_output)
    review_report = write_review_report(review_log, summary, args.review_report)
    recommendations_path, recommendations_report = write_outputs(
        recommendations,
        args.recommendations_output,
        args.recommendations_report,
    )
    print(f"sample_review_log: {review_path}")
    print(f"sample_review_summary: {summary_path}")
    print(f"sample_review_report: {review_report}")
    print(f"sample_rule_tuning_recommendations: {recommendations_path}")
    print(f"sample_rule_tuning_report: {recommendations_report}")


if __name__ == "__main__":
    main()
