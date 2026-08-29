"""Recommend rule-threshold tuning from incident review feedback."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.incident_review import (
    REVIEW_STATUS_CONFIRMED,
    REVIEW_STATUS_FALSE_ALARM,
    REVIEW_STATUS_NEEDS_DATA,
    REVIEW_STATUS_PENDING,
)

RULE_PATTERN = re.compile(r"\b([A-Za-z0-9_]+)\b")
RULE_PREFIXES = ("disease:", "management:", "environment:")


def _normalize_bool(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    return values.isin({"true", "1", "yes", "y", "확인", "맞음"})


def load_rule_config(config_path: str | Path) -> pd.DataFrame:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    rows = []
    for rule in config.get("rules", []):
        rows.append(
            {
                "rule_id": rule.get("id", ""),
                "category": rule.get("category", ""),
                "severity": rule.get("severity", ""),
                "feature": rule.get("feature", ""),
                "op": rule.get("op", ""),
                "threshold": rule.get("threshold", ""),
                "is_composite": bool(rule.get("all_of")),
                "note": rule.get("note", ""),
            }
        )
    return pd.DataFrame(rows)


def extract_rule_ids(reason: object, known_rule_ids: set[str]) -> list[str]:
    text = str(reason or "")
    found = []
    for token in RULE_PATTERN.findall(text):
        if token in known_rule_ids and token not in found:
            found.append(token)
    return found


def build_rule_feedback(review_log: pd.DataFrame, rule_config: pd.DataFrame) -> pd.DataFrame:
    known_rule_ids = set(rule_config["rule_id"].dropna().astype(str))
    rule_categories = dict(zip(rule_config["rule_id"].astype(str), rule_config["category"].astype(str)))
    df = review_log.copy()
    df["review_status"] = df.get("review_status", REVIEW_STATUS_PENDING).fillna(REVIEW_STATUS_PENDING).astype(str)
    df["confirmed_bool"] = _normalize_bool(df.get("confirmed", pd.Series(index=df.index, dtype=object)))
    df["false_alarm_bool"] = _normalize_bool(df.get("false_alarm", pd.Series(index=df.index, dtype=object)))

    rows = []
    for _, row in df.iterrows():
        row_queue = str(row.get("queue", ""))
        rule_ids = [
            rule_id
            for rule_id in extract_rule_ids(row.get("reason", ""), known_rule_ids)
            if rule_categories.get(rule_id, "") == row_queue
        ]
        for rule_id in rule_ids:
            rows.append(
                {
                    "rule_id": rule_id,
                    "queue": row.get("queue", ""),
                    "incident_id": row.get("incident_id", ""),
                    "review_status": row["review_status"],
                    "confirmed": bool(row["confirmed_bool"]) or row["review_status"] == REVIEW_STATUS_CONFIRMED,
                    "false_alarm": bool(row["false_alarm_bool"]) or row["review_status"] == REVIEW_STATUS_FALSE_ALARM,
                    "needs_data": row["review_status"] == REVIEW_STATUS_NEEDS_DATA,
                    "actual_cause": row.get("actual_cause", ""),
                    "max_track_score": row.get("max_track_score", 0.0),
                    "max_management_score": row.get("max_management_score", 0.0),
                    "max_environment_score": row.get("max_environment_score", 0.0),
                }
            )
    feedback = pd.DataFrame(rows)
    if feedback.empty:
        return pd.DataFrame(
            columns=[
                "rule_id",
                "category",
                "severity",
                "feature",
                "op",
                "threshold",
                "is_composite",
                "incidents",
                "reviewed",
                "confirmed",
                "false_alarm",
                "needs_data",
                "false_alarm_rate",
                "confirmed_rate",
                "recommendation",
                "rationale",
            ]
        )

    grouped = (
        feedback.groupby("rule_id", dropna=False)
        .agg(
            incidents=("incident_id", "nunique"),
            reviewed=("review_status", lambda s: int(s.ne(REVIEW_STATUS_PENDING).sum())),
            confirmed=("confirmed", "sum"),
            false_alarm=("false_alarm", "sum"),
            needs_data=("needs_data", "sum"),
        )
        .reset_index()
    )
    reviewed_decisions = grouped["confirmed"] + grouped["false_alarm"]
    grouped["false_alarm_rate"] = grouped["false_alarm"] / reviewed_decisions.replace(0, pd.NA)
    grouped["confirmed_rate"] = grouped["confirmed"] / reviewed_decisions.replace(0, pd.NA)
    merged = rule_config.merge(grouped, on="rule_id", how="left")
    count_cols = ["incidents", "reviewed", "confirmed", "false_alarm", "needs_data"]
    merged[count_cols] = merged[count_cols].fillna(0).astype(int)
    merged["false_alarm_rate"] = merged["false_alarm_rate"].astype("Float64")
    merged["confirmed_rate"] = merged["confirmed_rate"].astype("Float64")
    recommendation = merged.apply(_recommend_for_rule, axis=1, result_type="expand")
    merged["recommendation"] = recommendation[0]
    merged["rationale"] = recommendation[1]
    return merged.sort_values(
        ["reviewed", "false_alarm_rate", "confirmed_rate", "rule_id"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def _recommend_for_rule(row: pd.Series) -> tuple[str, str]:
    reviewed = int(row["reviewed"])
    false_alarm = int(row["false_alarm"])
    confirmed = int(row["confirmed"])
    if reviewed < 3:
        return "collect_more_reviews", "리뷰된 incident가 3건 미만이라 threshold 조정 근거가 부족함"

    decision_count = confirmed + false_alarm
    false_alarm_rate = float(false_alarm / decision_count) if decision_count else 0.0
    confirmed_rate = float(confirmed / decision_count) if decision_count else 0.0
    if false_alarm_rate >= 0.6:
        return "tighten_threshold", "오탐 비율이 높아 threshold를 더 보수적으로 조정하는 후보"
    if confirmed_rate >= 0.8:
        return "keep_or_relax_carefully", "확인 비율이 높아 현 기준 유지 또는 완화 검토 가능"
    if int(row["needs_data"]) > 0:
        return "improve_data_capture", "현장 확인에 추가 데이터가 필요하다는 표시가 있음"
    return "monitor", "확인/오탐이 혼재되어 추가 리뷰 후 판단"


def write_outputs(recommendations: pd.DataFrame, output_csv: str | Path, report_path: str | Path) -> tuple[Path, Path]:
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    recommendations.to_csv(output, index=False)

    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "rule_id",
        "category",
        "severity",
        "feature",
        "op",
        "threshold",
        "is_composite",
        "incidents",
        "reviewed",
        "confirmed",
        "false_alarm",
        "false_alarm_rate",
        "confirmed_rate",
        "recommendation",
        "rationale",
    ]
    actionable = recommendations[recommendations["reviewed"] > 0]
    lines = [
        "# Rule Tuning Recommendation 리포트",
        "",
        "## 요약",
        "",
        f"- 전체 rule: `{len(recommendations)}`",
        f"- 리뷰 근거가 있는 rule: `{len(actionable)}`",
        f"- threshold 강화 후보: `{int((recommendations['recommendation'] == 'tighten_threshold').sum())}`",
        f"- 유지/완화 검토 후보: `{int((recommendations['recommendation'] == 'keep_or_relax_carefully').sum())}`",
        f"- 추가 리뷰 필요: `{int((recommendations['recommendation'] == 'collect_more_reviews').sum())}`",
        "",
        "## Rule별 조정 후보",
        "",
        dataframe_to_markdown(recommendations[cols]),
        "",
        "## 적용 기준",
        "",
        "- `tighten_threshold`: 오탐률이 높으므로 더 강한 조건으로 조정 후보",
        "- `keep_or_relax_carefully`: 확인률이 높으므로 현재 기준 유지 또는 완화 검토",
        "- `collect_more_reviews`: 리뷰 수가 부족해 조정 보류",
        "- 실제 threshold 변경은 별도 실험 브랜치에서 lead-time/recall/precision을 비교한 뒤 반영한다.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend rule tuning from incident review feedback.")
    parser.add_argument("--review-log", default="data/templates/incident_review_log_template.csv")
    parser.add_argument("--rules-config", default="config/domain_rules.json")
    parser.add_argument("--output-csv", default="artifacts/rule_tuning_recommendations.csv")
    parser.add_argument("--report", default="artifacts/rule_tuning_recommendations_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review_log = pd.read_csv(args.review_log, low_memory=False)
    rule_config = load_rule_config(args.rules_config)
    recommendations = build_rule_feedback(review_log, rule_config)
    output, report = write_outputs(recommendations, args.output_csv, args.report)
    print(f"recommendations: {output}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
