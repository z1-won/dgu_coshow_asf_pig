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


def merge_incident_queue(existing_log: pd.DataFrame | None, incident_queue: pd.DataFrame) -> pd.DataFrame:
    """Bring the review log up to date with the current incident queue.

    Incidents already in ``existing_log`` keep whatever review state they
    have (pending or reviewed) instead of being reset -- this is what makes
    the log accumulate across runs instead of restarting blank every time.
    Incidents that only exist in ``incident_queue`` (new alerts) are added as
    pending. Incidents only in ``existing_log`` (e.g. the queue rotated them
    out) are kept as-is so past review history is never silently dropped.
    """
    fresh = build_review_log_template(incident_queue)
    if existing_log is None or existing_log.empty:
        return fresh

    existing_by_id = existing_log.set_index("incident_id")
    fresh_ids = set(fresh["incident_id"])
    rows = []
    for _, row in fresh.iterrows():
        incident_id = row["incident_id"]
        if incident_id in existing_by_id.index:
            merged = row.copy()
            for col in REVIEW_COLUMNS:
                merged[col] = existing_by_id.loc[incident_id, col]
            rows.append(merged)
        else:
            rows.append(row)
    carried_over = existing_log[~existing_log["incident_id"].isin(fresh_ids)]
    merged_df = pd.concat([pd.DataFrame(rows), carried_over], ignore_index=True)
    return merged_df[INCIDENT_COLUMNS + REVIEW_COLUMNS]


def apply_dashboard_reviews(review_log: pd.DataFrame, dashboard_export: pd.DataFrame) -> pd.DataFrame:
    """Apply confirm/dismiss decisions exported from the operator dashboard.

    ``dashboard_export`` is expected to have ``incident_id``, ``decision``
    (``"confirmed"`` or ``"dismissed"``) and ``resolved_at`` columns -- the
    shape produced by the dashboard's "리뷰 내보내기" export. Rows whose
    ``incident_id`` isn't in ``review_log`` are skipped rather than raising,
    since the dashboard's own incident list can lag the latest queue export.
    """
    log = review_log.set_index("incident_id")
    # All-empty review columns come back from a CSV round-trip as float64 NaN
    # (not the object dtype an in-memory pd.NA/"" column gets), and pandas 3
    # refuses to upcast that to bool/str via .loc assignment. Widen every
    # column this function writes into up front.
    for col in ("confirmed", "false_alarm", "resolved_at", "reviewed_by", "reviewed_at"):
        log[col] = log[col].astype(object)
    known_ids = set(log.index)
    skipped = 0
    for _, row in dashboard_export.iterrows():
        incident_id = row["incident_id"]
        if incident_id not in known_ids:
            skipped += 1
            continue
        decision = str(row.get("decision", "")).strip().lower()
        if decision == "confirmed":
            log.loc[incident_id, "review_status"] = REVIEW_STATUS_CONFIRMED
            log.loc[incident_id, "confirmed"] = True
            log.loc[incident_id, "false_alarm"] = False
        elif decision == "dismissed":
            log.loc[incident_id, "review_status"] = REVIEW_STATUS_FALSE_ALARM
            log.loc[incident_id, "confirmed"] = False
            log.loc[incident_id, "false_alarm"] = True
        else:
            continue
        log.loc[incident_id, "resolved_at"] = row.get("resolved_at", "")
        log.loc[incident_id, "reviewed_by"] = row.get("reviewed_by") or "dashboard_operator"
        log.loc[incident_id, "reviewed_at"] = row.get("resolved_at", "")
    if skipped:
        print(f"apply_dashboard_reviews: skipped {skipped} row(s) not present in review_log")
    return log.reset_index()[INCIDENT_COLUMNS + REVIEW_COLUMNS]


def apply_single_review(
    review_log: pd.DataFrame,
    incident_id: str,
    decision: str,
    reviewed_by: str | None = None,
    resolved_at: str | None = None,
) -> pd.DataFrame:
    """Apply one review decision -- the single-incident equivalent of
    ``apply_dashboard_reviews``, used by the FastAPI review endpoint so a
    click doesn't need to go through a CSV round-trip.

    Raises ``KeyError`` if ``incident_id`` isn't in ``review_log`` (the
    caller -- e.g. the API route -- is expected to turn that into a 404).
    """
    import datetime

    if incident_id not in set(review_log["incident_id"]):
        raise KeyError(incident_id)
    resolved_at = resolved_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    export_row = pd.DataFrame([{"incident_id": incident_id, "decision": decision, "resolved_at": resolved_at, "reviewed_by": reviewed_by}])
    return apply_dashboard_reviews(review_log, export_row)


def load_or_bootstrap_review_log(output_path: str | Path, incident_queue_path: str | Path) -> pd.DataFrame:
    """Load the persistent review log, creating/updating it from the current
    incident queue if it doesn't exist yet or is missing recently-added
    incidents. Shared by the CLI (``main``) and the API so both start from
    the same up-to-date state instead of two slightly different bootstraps."""
    output_path = Path(output_path)
    incident_queue = pd.read_csv(incident_queue_path, low_memory=False)
    existing_log = pd.read_csv(output_path, low_memory=False) if output_path.exists() else None
    return merge_incident_queue(existing_log, incident_queue)


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


def append_summary_history(summary: pd.DataFrame, history_path: str | Path) -> pd.DataFrame:
    """Append this run's summary to a growing history file, timestamped.

    ``summarize_review_log`` only ever reports the current point-in-time
    state -- without this, every run overwrites the last one and there is no
    way to see whether operator feedback (precision_estimate, reviewed
    count) is actually accumulating over time. This is what makes "운영자
    피드백 축적" observable, not just the review log itself growing.
    """
    import datetime

    snapshot = summary.copy()
    snapshot.insert(0, "snapshot_at", datetime.datetime.now(datetime.timezone.utc).isoformat())

    path = Path(history_path)
    if path.exists():
        prior = pd.read_csv(path, low_memory=False)
        combined = pd.concat([prior, snapshot], ignore_index=True)
    else:
        combined = snapshot
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)
    return combined


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
    parser = argparse.ArgumentParser(
        description=(
            "Build/update the persistent operator review log from incident_queue.csv. "
            "Re-running this keeps prior review decisions (--output-csv is loaded as the "
            "starting point if it already exists) instead of resetting to blank -- this is "
            "the project's accumulating incident review log, not a one-shot template."
        )
    )
    parser.add_argument("--incident-csv", default="artifacts/action_queues/incident_queue.csv")
    parser.add_argument("--output-csv", default="data/processed/incident_review_log.csv")
    parser.add_argument(
        "--dashboard-export",
        default=None,
        help="CSV exported from the dashboard's '리뷰 내보내기' button (incident_id, decision, resolved_at). Optional.",
    )
    parser.add_argument("--summary-output", default="artifacts/incident_review_summary.csv")
    parser.add_argument("--summary-history", default="data/processed/incident_review_summary_history.csv")
    parser.add_argument("--report", default="artifacts/incident_review_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review_log = load_or_bootstrap_review_log(args.output_csv, args.incident_csv)

    if args.dashboard_export:
        dashboard_export = pd.read_csv(args.dashboard_export, low_memory=False)
        review_log = apply_dashboard_reviews(review_log, dashboard_export)

    summary = summarize_review_log(review_log)

    output_csv = write_review_log(review_log, args.output_csv)
    summary_output = write_review_log(summary, args.summary_output)
    history = append_summary_history(summary, args.summary_history)
    report = write_report(review_log, summary, args.report)
    print(f"review_log: {output_csv} ({len(review_log)} incidents, {int(review_log['review_status'].ne(REVIEW_STATUS_PENDING).sum())} reviewed)")
    print(f"summary: {summary_output}")
    print(f"summary_history: {args.summary_history} ({len(history)} snapshots accumulated)")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
