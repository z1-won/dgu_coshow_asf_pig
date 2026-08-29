"""Report lead-time metrics separately by alert risk category."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.farm_event_schema import (
    DEFAULT_LEAD_TIME_HOURS,
    evaluate_lead_time,
    summarize_lead_time,
)

DEFAULT_CATEGORIES = ("final", "operational", "disease", "management", "environment")


def build_category_lead_time_metrics(
    events: pd.DataFrame,
    alerts: pd.DataFrame,
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
    horizons_hours: tuple[int, ...] = DEFAULT_LEAD_TIME_HOURS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_frames = []
    event_frames = []
    for category in categories:
        lead_matches, lead_event_summary = evaluate_lead_time(
            events,
            alerts,
            horizons_hours=horizons_hours,
            alert_category=category,
        )
        metrics = summarize_lead_time(
            lead_event_summary,
            lead_matches,
            alerts,
            horizons_hours=horizons_hours,
            alert_category=category,
        )
        metric_frames.append(metrics)
        lead_event_summary.insert(0, "alert_category_filter", category)
        event_frames.append(lead_event_summary)
    return pd.concat(metric_frames, ignore_index=True), pd.concat(event_frames, ignore_index=True)


def write_report(metrics: pd.DataFrame, events_by_category: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    all_scope = metrics[metrics["scope"] == "all"]
    lines = [
        "# Category별 Lead-Time 평가 리포트",
        "",
        "## 전체 요약",
        "",
        dataframe_to_markdown(all_scope),
        "",
        "## Event Type별 요약",
        "",
        dataframe_to_markdown(metrics[metrics["scope"] != "all"]),
        "",
        "## 이벤트별 Category 결과",
        "",
        dataframe_to_markdown(events_by_category),
        "",
        "## 해석 기준",
        "",
        "- `disease` recall은 수의학적 확인 우선 경보 성능을 본다.",
        "- `management` recall은 사료/급수 계열 운영 경보 성능을 본다.",
        "- `environment` recall은 CO2/NH3/환기 등 환경·설비 경보 성능을 본다.",
        "- `operational`은 세 category 중 하나라도 잡힌 경우를 본다.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build lead-time metrics by alert risk category.")
    parser.add_argument("--events", default="data/raw/farm_events/synthetic_mixed_events.csv")
    parser.add_argument("--alerts-csv", default="data/processed/final_chamber_anomaly_scores.csv")
    parser.add_argument("--categories", default="final,operational,disease,management,environment")
    parser.add_argument("--lead-hours", default="24,48,72")
    parser.add_argument("--metrics-output", default="artifacts/category_lead_time_metrics.csv")
    parser.add_argument("--events-output", default="artifacts/category_lead_time_events.csv")
    parser.add_argument("--report", default="artifacts/category_lead_time_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = pd.read_csv(args.events, low_memory=False)
    alerts = pd.read_csv(args.alerts_csv, low_memory=False)
    for col in ["start_datetime", "end_datetime"]:
        events[col] = pd.to_datetime(events[col], errors="coerce")
    categories = tuple(value.strip() for value in args.categories.split(",") if value.strip())
    horizons_hours = tuple(int(value.strip()) for value in args.lead_hours.split(",") if value.strip())

    metrics, events_by_category = build_category_lead_time_metrics(
        events,
        alerts,
        categories=categories,
        horizons_hours=horizons_hours,
    )

    metrics_output = Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_output, index=False)

    events_output = Path(args.events_output)
    events_by_category.to_csv(events_output, index=False)

    report = write_report(metrics, events_by_category, args.report)
    print(f"metrics: {metrics_output}")
    print(f"events: {events_output}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
