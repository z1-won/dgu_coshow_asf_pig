"""Create and summarize operator review logs for incident queues."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

REVIEW_STATUS_PENDING = "pending"
REVIEW_STATUS_CONFIRMED = "confirmed"
REVIEW_STATUS_FALSE_ALARM = "false_alarm"
REVIEW_STATUS_NEEDS_DATA = "needs_data"
REVIEW_STATUSES = (
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_CONFIRMED,
    REVIEW_STATUS_FALSE_ALARM,
    REVIEW_STATUS_NEEDS_DATA,
)

INCIDENT_COLUMNS = [
    "incident_id",
    "queue",
    "priority",
    "chamber_id",
    "incident_start_datetime",
    "incident_end_datetime",
    "window_count",
    "max_track_score",
    "max_management_score",
    "max_environment_score",
    "reason",
    "recommended_action",
]

REVIEW_COLUMNS = [
    "review_status",
    "confirmed",
    "false_alarm",
    "actual_cause",
    "resolved_at",
    "operator_note",
    "reviewed_by",
    "reviewed_at",
    "followup_required",
    "followup_action",
]


def build_review_log_template(incident_queue: pd.DataFrame) -> pd.DataFrame:
    """Return an incident review log with empty operator-feedback fields."""
    missing = [col for col in INCIDENT_COLUMNS if col not in incident_queue.columns]
    if missing:
        raise ValueError(f"incident_queue is missing required columns: {missing}")

    review_log = incident_queue[INCIDENT_COLUMNS].copy()
    review_log["review_status"] = REVIEW_STATUS_PENDING
    review_log["confirmed"] = pd.NA
    review_log["false_alarm"] = pd.NA
    review_log["actual_cause"] = ""
    review_log["resolved_at"] = ""
    review_log["operator_note"] = ""
    review_log["reviewed_by"] = ""
    review_log["reviewed_at"] = ""
    review_log["followup_required"] = False
    review_log["followup_action"] = ""
    return review_log[INCIDENT_COLUMNS + REVIEW_COLUMNS]


def _normalize_bool(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    return values.isin({"true", "1", "yes", "y", "확인", "맞음"})


def summarize_review_log(review_log: pd.DataFrame) -> pd.DataFrame:
    """Summarize review completion and feedback quality by queue."""
    if review_log.empty:
        return pd.DataFrame(
            [
                {
                    "scope": "all",
                    "incidents": 0,
                    "reviewed": 0,
                    "pending": 0,
                    "confirmed": 0,
                    "false_alarm": 0,
                    "needs_data": 0,
                    "precision_estimate": pd.NA,
                    "followup_required": 0,
                }
            ]
        )

    df = review_log.copy()
    df["review_status"] = df.get("review_status", REVIEW_STATUS_PENDING).fillna(REVIEW_STATUS_PENDING).astype(str)
    df["confirmed_bool"] = _normalize_bool(df.get("confirmed", pd.Series(index=df.index, dtype=object)))
    df["false_alarm_bool"] = _normalize_bool(df.get("false_alarm", pd.Series(index=df.index, dtype=object)))
    df["followup_bool"] = _normalize_bool(df.get("followup_required", pd.Series(index=df.index, dtype=object)))

    rows = []
    scopes: list[tuple[str, pd.DataFrame]] = [("all", df)]
    scopes += [(str(queue), group) for queue, group in df.groupby("queue", dropna=False)]
    for scope, group in scopes:
        reviewed = group["review_status"].ne(REVIEW_STATUS_PENDING)
        confirmed = group["confirmed_bool"] | group["review_status"].eq(REVIEW_STATUS_CONFIRMED)
        false_alarm = group["false_alarm_bool"] | group["review_status"].eq(REVIEW_STATUS_FALSE_ALARM)
        decision_count = int((confirmed | false_alarm).sum())
        precision_estimate = float(confirmed.sum() / decision_count) if decision_count else pd.NA
        rows.append(
            {
                "scope": scope,
                "incidents": int(len(group)),
                "reviewed": int(reviewed.sum()),
                "pending": int(group["review_status"].eq(REVIEW_STATUS_PENDING).sum()),
                "confirmed": int(confirmed.sum()),
                "false_alarm": int(false_alarm.sum()),
                "needs_data": int(group["review_status"].eq(REVIEW_STATUS_NEEDS_DATA).sum()),
                "precision_estimate": precision_estimate,
                "followup_required": int(group["followup_bool"].sum()),
            }
        )
    return pd.DataFrame(rows)


def write_review_log(review_log: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    review_log.to_csv(output, index=False)
    return output


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    if "reason" in display.columns:
        display["reason"] = display["reason"].astype(str).str.replace("|", ";", regex=False)
    return display


def write_report(review_log: pd.DataFrame, summary: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pending_cols = [
        "incident_id",
        "queue",
        "priority",
        "chamber_id",
        "incident_start_datetime",
        "incident_end_datetime",
        "reason",
        "recommended_action",
    ]
    pending = review_log[review_log["review_status"].eq(REVIEW_STATUS_PENDING)]
    lines = [
        "# Incident Review Log 리포트",
        "",
        "## 요약",
        "",
        dataframe_to_markdown(summary),
        "",
        "## 리뷰 입력값",
        "",
        "- `review_status`: pending, confirmed, false_alarm, needs_data 중 하나",
        "- `confirmed`: 현장 확인 결과 실제 문제였으면 true",
        "- `false_alarm`: 현장 확인 결과 오탐이면 true",
        "- `actual_cause`: 실제 원인. 예: fever, feed_supply_issue, water_line_blocked, ventilation_failure, sensor_error",
        "- `resolved_at`: 조치 완료 시각",
        "- `operator_note`: 현장 메모",
        "",
        "## Pending Incidents",
        "",
        dataframe_to_markdown(_display_frame(pending)[pending_cols]) if len(pending) else "대기 중 incident 없음.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator review log template from incident_queue.csv.")
    parser.add_argument("--incident-csv", default="artifacts/action_queues/incident_queue.csv")
    parser.add_argument("--output-csv", default="data/templates/incident_review_log_template.csv")
    parser.add_argument("--summary-output", default="artifacts/incident_review_summary.csv")
    parser.add_argument("--report", default="artifacts/incident_review_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    incident_queue = pd.read_csv(args.incident_csv, low_memory=False)
    review_log = build_review_log_template(incident_queue)
    summary = summarize_review_log(review_log)

    output_csv = write_review_log(review_log, args.output_csv)
    summary_output = write_review_log(summary, args.summary_output)
    report = write_report(review_log, summary, args.report)
    print(f"review_log: {output_csv}")
    print(f"summary: {summary_output}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
