"""Build operational action queues from final chamber alert outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

QUEUE_CATEGORIES = ("disease", "management", "environment")
DEFAULT_INCIDENT_GAP_HOURS = 24


def _has_category(value: object, category: str) -> bool:
    categories = {part.strip() for part in str(value or "").split(",") if part.strip()}
    return category in categories


def _reason_contains(row: pd.Series, token: str) -> bool:
    return token in str(row.get("reason", ""))


def _action_for(category: str, row: pd.Series) -> str:
    if category == "disease":
        if _reason_contains(row, "rectal_temp_high"):
            return "체온 상승 개체 확인, 증상 관찰, 격리 필요성 판단, 수의사 확인"
        return "개체 상태 확인, 이상행동/체온 재점검, 수의사 확인"
    if category == "management":
        if _reason_contains(row, "feed_drop"):
            return "급이기 작동, 사료 잔량, 급이 스케줄, 섭취 저하 원인 확인"
        if _reason_contains(row, "water_drop"):
            return "급수기 막힘, 수압, 음수 라인, 누수/단수 여부 확인"
        return "사료/급수 설비와 사양관리 변경 사항 확인"
    if category == "environment":
        if _reason_contains(row, "barn_temp_high"):
            return "고온/열스트레스 가능성 확인, 냉방/환기/온습도 센서와 CCTV 상태 확인"
        if _reason_contains(row, "co2_high") and _reason_contains(row, "nh3_high"):
            return "환기량 증대, CO2/NH3 센서 재확인, 분뇨/환기 설비 점검"
        if _reason_contains(row, "co2_high"):
            return "CO2 농도와 환기팬/입기구 상태 확인"
        if _reason_contains(row, "nh3_high"):
            return "NH3 농도, 분뇨 상태, 환기 상태 확인"
        if _reason_contains(row, "ventilation_low"):
            return "환기팬, 컨트롤러, 입기구, 설정값 확인"
        return "온습도/가스/환기 센서와 설비 상태 확인"
    return "현장 확인"


def _severity_for(category: str, row: pd.Series) -> tuple[int, str]:
    track_score = float(row.get("track_score", 0.0) or 0.0)
    management_score = float(row.get("management_score", 0.0) or 0.0)
    environment_score = float(row.get("environment_score", 0.0) or 0.0)
    tier = str(row.get("tier", "normal") or "normal")

    if category == "disease":
        if tier == "high" or track_score >= 1.5:
            return 1, "urgent"
        if track_score >= 1.0:
            return 2, "high"
        return 3, "watch"
    if category == "environment":
        if environment_score >= 1.2:
            return 1, "urgent"
        return 2, "high"
    if category == "management":
        if management_score >= 0.8:
            return 2, "high"
        return 3, "watch"
    return 4, "review"


def build_action_queue(alerts: pd.DataFrame, categories: tuple[str, ...] = QUEUE_CATEGORIES) -> pd.DataFrame:
    """Expand final alerts into one action row per relevant risk category."""
    rows: list[dict[str, object]] = []
    for _, row in alerts.iterrows():
        for category in categories:
            if not _has_category(row.get("alert_category", ""), category):
                continue
            priority_rank, priority = _severity_for(category, row)
            rows.append(
                {
                    "queue": category,
                    "priority_rank": priority_rank,
                    "priority": priority,
                    "track": row.get("track", ""),
                    "source_dataset": row.get("source_dataset", ""),
                    "chamber_id": row.get("chamber_id", ""),
                    "start_datetime": row.get("start_datetime", ""),
                    "end_datetime": row.get("end_datetime", ""),
                    "track_score": row.get("track_score", 0.0),
                    "management_score": row.get("management_score", 0.0),
                    "environment_score": row.get("environment_score", 0.0),
                    "tier": row.get("tier", ""),
                    "reason": row.get("reason", ""),
                    "recommended_action": _action_for(category, row),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "queue",
                "priority_rank",
                "priority",
                "track",
                "source_dataset",
                "chamber_id",
                "start_datetime",
                "end_datetime",
                "track_score",
                "management_score",
                "environment_score",
                "tier",
                "reason",
                "recommended_action",
            ]
        )

    queue = pd.DataFrame(rows)
    queue["start_datetime"] = pd.to_datetime(queue["start_datetime"], errors="coerce")
    queue["end_datetime"] = pd.to_datetime(queue["end_datetime"], errors="coerce")
    return queue.sort_values(
        ["priority_rank", "track_score", "environment_score", "management_score", "start_datetime"],
        ascending=[True, False, False, False, True],
    ).reset_index(drop=True)


def write_action_queues(queue: pd.DataFrame, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    paths = {"combined": output / "combined_action_queue.csv"}
    queue.to_csv(paths["combined"], index=False)
    for category in QUEUE_CATEGORIES:
        paths[category] = output / f"{category}_queue.csv"
        queue[queue["queue"] == category].to_csv(paths[category], index=False)
    return paths


def _summarize_incident(rows: list[pd.Series]) -> dict[str, object]:
    frame = pd.DataFrame(rows)
    priority_rank = int(frame["priority_rank"].min())
    priority = str(frame.sort_values("priority_rank").iloc[0]["priority"])
    return {
        "queue": frame["queue"].iloc[0],
        "priority_rank": priority_rank,
        "priority": priority,
        "track": ",".join(sorted({str(value) for value in frame["track"].dropna()})),
        "source_dataset": ",".join(sorted({str(value) for value in frame["source_dataset"].dropna()})),
        "chamber_id": frame["chamber_id"].iloc[0],
        "incident_start_datetime": frame["start_datetime"].min(),
        "incident_end_datetime": frame["end_datetime"].max(),
        "window_count": int(len(frame)),
        "max_track_score": float(frame["track_score"].max()),
        "max_management_score": float(frame["management_score"].max()),
        "max_environment_score": float(frame["environment_score"].max()),
        "tier": ",".join(sorted({str(value) for value in frame["tier"].dropna() if str(value)})),
        "reason": frame["reason"].iloc[0],
        "recommended_action": frame["recommended_action"].iloc[0],
    }


def build_incident_queue(queue: pd.DataFrame, max_gap_hours: int = DEFAULT_INCIDENT_GAP_HOURS) -> pd.DataFrame:
    """Collapse adjacent action windows into incident-level rows."""
    columns = [
        "incident_id",
        "queue",
        "priority_rank",
        "priority",
        "track",
        "source_dataset",
        "chamber_id",
        "incident_start_datetime",
        "incident_end_datetime",
        "window_count",
        "max_track_score",
        "max_management_score",
        "max_environment_score",
        "tier",
        "reason",
        "recommended_action",
    ]
    if queue.empty:
        return pd.DataFrame(columns=columns)

    ordered = queue.copy()
    ordered["start_datetime"] = pd.to_datetime(ordered["start_datetime"], errors="coerce")
    ordered["end_datetime"] = pd.to_datetime(ordered["end_datetime"], errors="coerce")
    ordered = ordered.sort_values(["queue", "chamber_id", "reason", "start_datetime", "end_datetime"])
    max_gap = pd.Timedelta(hours=max_gap_hours)
    incidents: list[dict[str, object]] = []

    for _, group in ordered.groupby(["queue", "chamber_id", "reason"], dropna=False):
        current_rows: list[pd.Series] = []
        current_end = pd.NaT
        for _, row in group.iterrows():
            start = row["start_datetime"]
            end = row["end_datetime"]
            starts_new = not current_rows
            if current_rows and pd.notna(start) and pd.notna(current_end):
                starts_new = start > current_end + max_gap
            if starts_new and current_rows:
                incidents.append(_summarize_incident(current_rows))
                current_rows = []
            current_rows.append(row)
            if pd.isna(current_end) or (pd.notna(end) and end > current_end):
                current_end = end
        if current_rows:
            incidents.append(_summarize_incident(current_rows))

    incident_df = pd.DataFrame(incidents, columns=[col for col in columns if col != "incident_id"])
    incident_df = incident_df.sort_values(
        ["priority_rank", "max_track_score", "max_environment_score", "max_management_score", "incident_start_datetime"],
        ascending=[True, False, False, False, True],
    ).reset_index(drop=True)
    category_counts: dict[str, int] = {}
    incident_ids = []
    for _, row in incident_df.iterrows():
        category = str(row.queue)
        category_counts[category] = category_counts.get(category, 0) + 1
        incident_ids.append(f"{category}-{category_counts[category]:04d}")
    incident_df.insert(0, "incident_id", incident_ids)
    return incident_df[columns]


def write_incident_queue(incident_queue: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    incident_queue.to_csv(output, index=False)
    return output


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    if "reason" in display.columns:
        display["reason"] = display["reason"].astype(str).str.replace("|", ";", regex=False)
    return display


def write_report(queue: pd.DataFrame, output_path: str | Path, incident_queue: pd.DataFrame | None = None) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = queue["queue"].value_counts() if len(queue) else pd.Series(dtype=int)
    report_cols = [
        "priority",
        "chamber_id",
        "start_datetime",
        "track_score",
        "management_score",
        "environment_score",
        "reason",
        "recommended_action",
    ]
    display_queue = _display_frame(queue)

    lines = [
        "# Category Action Queue 리포트",
        "",
        "## 요약",
        "",
        f"- 전체 action item: `{len(queue)}`",
        f"- disease queue: `{int(counts.get('disease', 0))}`",
        f"- management queue: `{int(counts.get('management', 0))}`",
        f"- environment queue: `{int(counts.get('environment', 0))}`",
    ]
    if incident_queue is not None:
        incident_counts = incident_queue["queue"].value_counts() if len(incident_queue) else pd.Series(dtype=int)
        incident_cols = [
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
        lines += [
            f"- incident: `{len(incident_queue)}`",
            f"- disease incident: `{int(incident_counts.get('disease', 0))}`",
            f"- management incident: `{int(incident_counts.get('management', 0))}`",
            f"- environment incident: `{int(incident_counts.get('environment', 0))}`",
            "",
            "## Incident Queue",
            "",
            dataframe_to_markdown(_display_frame(incident_queue)[incident_cols]) if len(incident_queue) else "해당 없음.",
            "",
        ]
    lines += [
        "## Disease Queue",
        "",
        dataframe_to_markdown(display_queue[display_queue["queue"] == "disease"][report_cols])
        if int(counts.get("disease", 0))
        else "해당 없음.",
        "",
        "## Management Queue",
        "",
        dataframe_to_markdown(display_queue[display_queue["queue"] == "management"][report_cols])
        if int(counts.get("management", 0))
        else "해당 없음.",
        "",
        "## Environment Queue",
        "",
        dataframe_to_markdown(display_queue[display_queue["queue"] == "environment"][report_cols])
        if int(counts.get("environment", 0))
        else "해당 없음.",
        "",
        "## 사용 기준",
        "",
        "- `disease`는 수의학적 확인과 질병 의심 대응을 우선한다.",
        "- `management`는 급이/급수/사양관리 확인을 우선한다.",
        "- `environment`는 환기, CO2, NH3, 온습도와 설비 확인을 우선한다.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build category-specific operational action queues.")
    parser.add_argument("--alerts-csv", default="data/processed/final_chamber_anomaly_scores.csv")
    parser.add_argument("--output-dir", default="artifacts/action_queues")
    parser.add_argument("--report", default="artifacts/action_queues/action_queue_report.md")
    parser.add_argument("--incident-output", default="")
    parser.add_argument("--max-incident-gap-hours", type=int, default=DEFAULT_INCIDENT_GAP_HOURS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    alerts = pd.read_csv(args.alerts_csv, low_memory=False)
    if "operational_alert" in alerts.columns:
        alerts = alerts[alerts["operational_alert"].astype(bool)].copy()
    elif "final_alert" in alerts.columns:
        alerts = alerts[alerts["final_alert"].astype(bool)].copy()

    queue = build_action_queue(alerts)
    incident_queue = build_incident_queue(queue, max_gap_hours=args.max_incident_gap_hours)
    paths = write_action_queues(queue, args.output_dir)
    incident_output = Path(args.incident_output) if args.incident_output else Path(args.output_dir) / "incident_queue.csv"
    incident_path = write_incident_queue(incident_queue, incident_output)
    report = write_report(queue, args.report, incident_queue=incident_queue)
    print(f"combined: {paths['combined']}")
    print(f"disease: {paths['disease']}")
    print(f"management: {paths['management']}")
    print(f"environment: {paths['environment']}")
    print(f"incident: {incident_path}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
