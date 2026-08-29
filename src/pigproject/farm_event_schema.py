"""Validate real-farm event logs and match them to final alert windows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

REQUIRED_COLUMNS = [
    "event_id",
    "farm_id",
    "chamber_id",
    "event_type",
    "start_datetime",
    "end_datetime",
    "severity",
    "vet_confirmed",
    "source",
    "notes",
]

EVENT_TYPES = {
    "asf_suspected",
    "asf_confirmed",
    "fever",
    "respiratory",
    "feed_drop",
    "water_drop",
    "mortality",
    "treatment",
    "vaccination",
    "environment_failure",
    "equipment_failure",
    "movement",
    "other",
}

BOOLEAN_TRUE = {"true", "t", "yes", "y", "1"}
BOOLEAN_FALSE = {"false", "f", "no", "n", "0"}
DEFAULT_LEAD_TIME_HOURS = (24, 48, 72)


@dataclass(frozen=True)
class ValidationResult:
    cleaned: pd.DataFrame
    issues: pd.DataFrame


def template_dataframe() -> pd.DataFrame:
    """Return an empty-but-illustrative farm event template."""
    return pd.DataFrame(
        [
            {
                "event_id": "evt-0001",
                "farm_id": "farm-a",
                "chamber_id": "bioenergy:71408:1",
                "event_type": "fever",
                "start_datetime": "2023-01-01 08:00:00",
                "end_datetime": "2023-01-01 18:00:00",
                "severity": 3,
                "vet_confirmed": "false",
                "source": "farm_log",
                "notes": "example row; replace with real event details",
            }
        ],
        columns=REQUIRED_COLUMNS,
    )


def write_template(path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    template_dataframe().to_csv(output, index=False)
    return output


def _issue(row_number: int | None, column: str, severity: str, message: str) -> dict:
    return {"row_number": row_number, "column": column, "severity": severity, "message": message}


def _parse_bool(value: object) -> bool | pd.NA:
    if pd.isna(value):
        return pd.NA
    lowered = str(value).strip().lower()
    if lowered in BOOLEAN_TRUE:
        return True
    if lowered in BOOLEAN_FALSE:
        return False
    return pd.NA


def validate_events(df: pd.DataFrame) -> ValidationResult:
    """Validate and normalize a real-farm event table.

    row_number is reported as a 1-based CSV data row number, excluding the
    header, so it is easy to find the problematic line in a spreadsheet.
    """
    issues: list[dict] = []
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    for col in missing:
        issues.append(_issue(None, col, "error", "required column is missing"))

    cleaned = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in cleaned.columns:
            cleaned[col] = pd.NA
    cleaned = cleaned[REQUIRED_COLUMNS + [col for col in cleaned.columns if col not in REQUIRED_COLUMNS]].copy()

    for text_col in ["event_id", "farm_id", "chamber_id", "event_type", "source", "notes"]:
        cleaned[text_col] = cleaned[text_col].fillna("").astype(str).str.strip()

    cleaned["start_datetime"] = pd.to_datetime(cleaned["start_datetime"], errors="coerce")
    cleaned["end_datetime"] = pd.to_datetime(cleaned["end_datetime"], errors="coerce")
    cleaned["severity"] = pd.to_numeric(cleaned["severity"], errors="coerce")
    cleaned["vet_confirmed"] = cleaned["vet_confirmed"].apply(_parse_bool)

    seen_event_ids: set[str] = set()
    for index, row in cleaned.iterrows():
        row_number = int(index) + 1
        event_id = row["event_id"]
        if not event_id:
            issues.append(_issue(row_number, "event_id", "error", "event_id is empty"))
        elif event_id in seen_event_ids:
            issues.append(_issue(row_number, "event_id", "error", f"duplicate event_id: {event_id}"))
        seen_event_ids.add(event_id)

        if not row["farm_id"]:
            issues.append(_issue(row_number, "farm_id", "error", "farm_id is empty"))
        if not row["chamber_id"]:
            issues.append(_issue(row_number, "chamber_id", "error", "chamber_id is empty"))

        if row["event_type"] not in EVENT_TYPES:
            issues.append(
                _issue(
                    row_number,
                    "event_type",
                    "error",
                    f"event_type must be one of: {', '.join(sorted(EVENT_TYPES))}",
                )
            )

        if pd.isna(row["start_datetime"]):
            issues.append(_issue(row_number, "start_datetime", "error", "start_datetime is not parseable"))
        if pd.isna(row["end_datetime"]):
            issues.append(_issue(row_number, "end_datetime", "error", "end_datetime is not parseable"))
        if pd.notna(row["start_datetime"]) and pd.notna(row["end_datetime"]) and row["end_datetime"] < row["start_datetime"]:
            issues.append(_issue(row_number, "end_datetime", "error", "end_datetime is before start_datetime"))

        if pd.isna(row["severity"]) or not 1 <= float(row["severity"]) <= 5:
            issues.append(_issue(row_number, "severity", "error", "severity must be a number from 1 to 5"))
        if pd.isna(row["vet_confirmed"]):
            issues.append(_issue(row_number, "vet_confirmed", "error", "vet_confirmed must be true/false"))

    return ValidationResult(cleaned=cleaned, issues=pd.DataFrame(issues))


def _overlap_hours(a_start: pd.Timestamp, a_end: pd.Timestamp, b_start: pd.Timestamp, b_end: pd.Timestamp) -> float:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if pd.isna(start) or pd.isna(end) or end <= start:
        return 0.0
    return float((end - start).total_seconds() / 3600)


def match_events_to_alerts(events: pd.DataFrame, alerts: pd.DataFrame) -> pd.DataFrame:
    """Match event rows to final ensemble windows by chamber_id and time overlap."""
    event_rows = events.copy()
    alert_rows = alerts.copy()
    alert_rows["start_datetime"] = pd.to_datetime(alert_rows["start_datetime"], errors="coerce")
    alert_rows["end_datetime"] = pd.to_datetime(alert_rows["end_datetime"], errors="coerce")
    if "final_alert" in alert_rows.columns:
        alert_rows = alert_rows[alert_rows["final_alert"].astype(bool)]

    matches: list[dict] = []
    for _, event in event_rows.iterrows():
        candidates = alert_rows[alert_rows["chamber_id"].astype(str) == str(event["chamber_id"])]
        for _, alert in candidates.iterrows():
            overlap = _overlap_hours(
                event["start_datetime"],
                event["end_datetime"],
                alert["start_datetime"],
                alert["end_datetime"],
            )
            if overlap > 0:
                matches.append(
                    {
                        "event_id": event["event_id"],
                        "farm_id": event["farm_id"],
                        "chamber_id": event["chamber_id"],
                        "event_type": event["event_type"],
                        "event_start_datetime": event["start_datetime"],
                        "event_end_datetime": event["end_datetime"],
                        "severity": event["severity"],
                        "vet_confirmed": event["vet_confirmed"],
                        "alert_track": alert.get("track", ""),
                        "alert_start_datetime": alert["start_datetime"],
                        "alert_end_datetime": alert["end_datetime"],
                        "track_score": alert.get("track_score", pd.NA),
                        "tier": alert.get("tier", ""),
                        "reason": alert.get("reason", ""),
                        "overlap_hours": overlap,
                    }
                )
    return pd.DataFrame(matches)


def filter_alerts_by_category(alerts: pd.DataFrame, category: str = "final") -> pd.DataFrame:
    """Filter alert rows for final, operational, or a named alert category."""
    alert_rows = alerts.copy()
    if category == "operational":
        if "operational_alert" in alert_rows.columns:
            return alert_rows[alert_rows["operational_alert"].astype(bool)]
        if "final_alert" in alert_rows.columns:
            return alert_rows[alert_rows["final_alert"].astype(bool)]
        return alert_rows
    if category == "final":
        if "final_alert" in alert_rows.columns:
            return alert_rows[alert_rows["final_alert"].astype(bool)]
        return alert_rows
    if "alert_category" not in alert_rows.columns:
        return alert_rows.iloc[0:0].copy()
    category_tokens = alert_rows["alert_category"].fillna("").astype(str).str.split(",")
    return alert_rows[category_tokens.apply(lambda values: category in values)]


def evaluate_lead_time(
    events: pd.DataFrame,
    alerts: pd.DataFrame,
    horizons_hours: tuple[int, ...] = DEFAULT_LEAD_TIME_HOURS,
    alert_category: str = "final",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate whether alerts fired before event start within configured horizons."""
    event_rows = events.copy()
    alert_rows = filter_alerts_by_category(alerts, alert_category)
    alert_rows["start_datetime"] = pd.to_datetime(alert_rows["start_datetime"], errors="coerce")
    alert_rows["end_datetime"] = pd.to_datetime(alert_rows["end_datetime"], errors="coerce")

    max_horizon = max(horizons_hours)
    match_rows: list[dict] = []
    event_summary_rows: list[dict] = []

    for _, event in event_rows.iterrows():
        event_start = event["start_datetime"]
        candidates = alert_rows[alert_rows["chamber_id"].astype(str) == str(event["chamber_id"])]
        candidates = candidates[candidates["start_datetime"].notna()]
        candidates = candidates[candidates["start_datetime"] <= event_start]
        if pd.notna(event_start):
            lead_hours = (event_start - candidates["start_datetime"]).dt.total_seconds() / 3600
            candidates = candidates[(lead_hours >= 0) & (lead_hours <= max_horizon)].copy()
            candidates["lead_hours"] = lead_hours.loc[candidates.index]
        else:
            candidates = candidates.iloc[0:0].copy()
            candidates["lead_hours"] = pd.Series(dtype=float)

        for _, alert in candidates.iterrows():
            lead_hours_value = float(alert["lead_hours"])
            matched_horizons = [h for h in horizons_hours if lead_hours_value <= h]
            match_rows.append(
                {
                    "event_id": event["event_id"],
                    "farm_id": event["farm_id"],
                    "chamber_id": event["chamber_id"],
                    "event_type": event["event_type"],
                    "event_start_datetime": event["start_datetime"],
                    "event_end_datetime": event["end_datetime"],
                    "severity": event["severity"],
                    "vet_confirmed": event["vet_confirmed"],
                    "alert_track": alert.get("track", ""),
                    "alert_category": alert.get("alert_category", ""),
                    "alert_start_datetime": alert["start_datetime"],
                    "alert_end_datetime": alert["end_datetime"],
                    "track_score": alert.get("track_score", pd.NA),
                    "tier": alert.get("tier", ""),
                    "reason": alert.get("reason", ""),
                    "lead_hours": lead_hours_value,
                    "matched_horizons_hours": ",".join(str(h) for h in matched_horizons),
                }
            )

        if len(candidates):
            first_alert = candidates.sort_values("start_datetime").iloc[0]
            best_score = candidates["track_score"].max() if "track_score" in candidates else pd.NA
            first_lead_hours = float(first_alert["lead_hours"])
        else:
            first_alert = None
            best_score = pd.NA
            first_lead_hours = pd.NA

        summary = {
            "event_id": event["event_id"],
            "farm_id": event["farm_id"],
            "chamber_id": event["chamber_id"],
            "event_type": event["event_type"],
            "expected_rule": event.get("expected_rule", ""),
            "event_start_datetime": event["start_datetime"],
            "severity": event["severity"],
            "vet_confirmed": event["vet_confirmed"],
            "lead_alert_count": len(candidates),
            "first_alert_start_datetime": first_alert["start_datetime"] if first_alert is not None else pd.NaT,
            "first_lead_hours": first_lead_hours,
            "max_track_score": best_score,
        }
        for horizon in horizons_hours:
            summary[f"caught_within_{horizon}h"] = bool(len(candidates[candidates["lead_hours"] <= horizon]))
        event_summary_rows.append(summary)

    return pd.DataFrame(match_rows), pd.DataFrame(event_summary_rows)


def summarize_lead_time(
    lead_event_summary: pd.DataFrame,
    lead_matches: pd.DataFrame,
    alerts: pd.DataFrame,
    horizons_hours: tuple[int, ...] = DEFAULT_LEAD_TIME_HOURS,
    alert_category: str = "final",
) -> pd.DataFrame:
    """Build event-level recall and alert-level precision-proxy metrics."""
    if len(lead_event_summary) == 0:
        return pd.DataFrame(columns=["scope", "events", "lead_matched_events", "recall_24h", "recall_48h", "recall_72h"])

    alert_rows = filter_alerts_by_category(alerts, alert_category)
    matched_alerts = (
        lead_matches[["chamber_id", "alert_start_datetime", "alert_end_datetime"]].drop_duplicates()
        if len(lead_matches)
        else pd.DataFrame(columns=["chamber_id", "alert_start_datetime", "alert_end_datetime"])
    )

    rows: list[dict] = []
    for scope_name, group in [("all", lead_event_summary)] + list(lead_event_summary.groupby("event_type", dropna=False)):
        row = {
            "scope": scope_name,
            "alert_category_filter": alert_category,
            "events": len(group),
            "lead_matched_events": int((group["lead_alert_count"] > 0).sum()),
            "mean_first_lead_hours": group["first_lead_hours"].dropna().mean() if group["first_lead_hours"].notna().any() else pd.NA,
            "max_first_lead_hours": group["first_lead_hours"].dropna().max() if group["first_lead_hours"].notna().any() else pd.NA,
            "total_alert_windows": len(alert_rows),
            "lead_matched_alert_windows": len(matched_alerts),
            "precision_proxy": len(matched_alerts) / len(alert_rows) if len(alert_rows) else pd.NA,
        }
        for horizon in horizons_hours:
            col = f"caught_within_{horizon}h"
            row[f"recall_{horizon}h"] = float(group[col].mean()) if len(group) else pd.NA
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(
    events: pd.DataFrame,
    issues: pd.DataFrame,
    matches: pd.DataFrame,
    lead_matches: pd.DataFrame,
    lead_event_summary: pd.DataFrame,
    lead_metrics: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    error_count = int((issues["severity"] == "error").sum()) if len(issues) else 0
    event_summary = (
        events.groupby("event_type", dropna=False)
        .agg(events=("event_id", "count"), mean_severity=("severity", "mean"))
        .reset_index()
        if len(events)
        else pd.DataFrame(columns=["event_type", "events", "mean_severity"])
    )
    chamber_summary = (
        events.groupby("chamber_id", dropna=False)
        .agg(events=("event_id", "count"), max_severity=("severity", "max"))
        .reset_index()
        if len(events)
        else pd.DataFrame(columns=["chamber_id", "events", "max_severity"])
    )

    lines = [
        "# 실제 농장 이벤트 데이터 검증 리포트",
        "",
        "## 요약",
        "",
        f"- 이벤트 row: `{len(events)}`",
        f"- schema error: `{error_count}`",
        f"- 최종 경보와 시간 겹침 match: `{len(matches)}`",
        f"- lead-time 사전 경보 match: `{len(lead_matches)}`",
        "",
        "## 이벤트 유형별 요약",
        "",
        dataframe_to_markdown(event_summary),
        "",
        "## 돈방별 이벤트 요약",
        "",
        dataframe_to_markdown(chamber_summary),
        "",
        "## Schema 이슈",
        "",
        dataframe_to_markdown(issues) if len(issues) else "이슈 없음.",
        "",
        "## 최종 경보와 겹친 이벤트",
        "",
        dataframe_to_markdown(matches) if len(matches) else "겹친 이벤트 없음.",
        "",
        "## Lead-Time 평가 요약",
        "",
        dataframe_to_markdown(lead_metrics) if len(lead_metrics) else "lead-time 평가 대상 없음.",
        "",
        "## 이벤트별 Lead-Time 결과",
        "",
        dataframe_to_markdown(lead_event_summary) if len(lead_event_summary) else "lead-time 이벤트 요약 없음.",
        "",
        "## Lead-Time 사전 경보 Match",
        "",
        dataframe_to_markdown(lead_matches) if len(lead_matches) else "사전 경보 match 없음.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate farm event logs and match them to final alert windows.")
    parser.add_argument("--input", help="Farm event CSV to validate.")
    parser.add_argument("--template-output", default="data/templates/farm_event_log_template.csv")
    parser.add_argument("--clean-output", default="data/processed/farm_event_log_clean.csv")
    parser.add_argument("--issues-output", default="artifacts/farm_event_schema_issues.csv")
    parser.add_argument("--alerts-csv", default="data/processed/final_chamber_anomaly_scores.csv")
    parser.add_argument("--matches-output", default="artifacts/farm_event_alert_matches.csv")
    parser.add_argument("--lead-matches-output", default="artifacts/farm_event_lead_time_matches.csv")
    parser.add_argument("--lead-summary-output", default="artifacts/farm_event_lead_time_summary.csv")
    parser.add_argument("--lead-hours", default="24,48,72", help="Comma-separated lead-time horizons in hours.")
    parser.add_argument("--alert-category", default="final", help="final, operational, disease, management, or environment.")
    parser.add_argument("--report", default="artifacts/farm_event_schema_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template_path = write_template(args.template_output)

    if not args.input:
        print(f"template: {template_path}")
        print("No --input provided; wrote template only.")
        return

    events = pd.read_csv(args.input, low_memory=False)
    result = validate_events(events)

    clean_output = Path(args.clean_output)
    clean_output.parent.mkdir(parents=True, exist_ok=True)
    result.cleaned.to_csv(clean_output, index=False)

    issues_output = Path(args.issues_output)
    issues_output.parent.mkdir(parents=True, exist_ok=True)
    result.issues.to_csv(issues_output, index=False)

    matches = pd.DataFrame()
    lead_matches = pd.DataFrame()
    lead_event_summary = pd.DataFrame()
    lead_metrics = pd.DataFrame()
    alerts_path = Path(args.alerts_csv)
    horizons_hours = tuple(int(value.strip()) for value in args.lead_hours.split(",") if value.strip())
    if alerts_path.exists():
        alerts = pd.read_csv(alerts_path, low_memory=False)
        matches = match_events_to_alerts(result.cleaned, alerts)
        lead_matches, lead_event_summary = evaluate_lead_time(
            result.cleaned, alerts, horizons_hours, alert_category=args.alert_category
        )
        lead_metrics = summarize_lead_time(
            lead_event_summary, lead_matches, alerts, horizons_hours, alert_category=args.alert_category
        )

    matches_output = Path(args.matches_output)
    matches_output.parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(matches_output, index=False)

    lead_matches_output = Path(args.lead_matches_output)
    lead_matches_output.parent.mkdir(parents=True, exist_ok=True)
    lead_matches.to_csv(lead_matches_output, index=False)

    lead_summary_output = Path(args.lead_summary_output)
    lead_summary_output.parent.mkdir(parents=True, exist_ok=True)
    lead_event_summary.to_csv(lead_summary_output, index=False)

    report_path = write_report(
        result.cleaned,
        result.issues,
        matches,
        lead_matches,
        lead_event_summary,
        lead_metrics,
        args.report,
    )
    error_count = int((result.issues["severity"] == "error").sum()) if len(result.issues) else 0
    print(f"template: {template_path}")
    print(f"clean events: {clean_output}")
    print(f"issues: {issues_output}")
    print(f"matches: {matches_output}")
    print(f"lead matches: {lead_matches_output}")
    print(f"lead summary: {lead_summary_output}")
    print(f"report: {report_path}")
    print(f"schema errors: {error_count}")


if __name__ == "__main__":
    main()
