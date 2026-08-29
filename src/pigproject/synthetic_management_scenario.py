"""Create a final-ensemble-ready synthetic management alert scenario."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

TEXT_COLUMNS = [
    "rule_reasons",
    "disease_rule_reasons",
    "management_rule_reasons",
    "environment_rule_reasons",
    "alert_category",
    "primary_reason",
    "disease_tier",
]

NUMERIC_COLUMNS = [
    "rule_triggered_count",
    "rule_severity_sum",
    "rule_co_occurrence_bonus",
    "rule_score",
    "disease_rule_score",
    "management_rule_score",
    "environment_rule_score",
    "rule_component",
    "disease_score",
    "management_score",
    "environment_score",
    "model_component",
]

BOOLEAN_COLUMNS = [
    "rule_observation",
    "rule_anomaly",
    "disease_rule_anomaly",
    "management_rule_anomaly",
    "environment_rule_anomaly",
    "model_anomaly",
    "management_alert",
    "environment_alert",
    "disease_alert",
    "final_alert",
]


def _inject_management_alert(row: pd.Series, rule_id: str) -> pd.Series:
    row = row.copy()
    row[f"rule_{rule_id}"] = True
    row["rule_reasons"] = rule_id
    row["rule_triggered_count"] = 1
    row["rule_severity_sum"] = 0.6
    row["rule_co_occurrence_bonus"] = 0.0
    row["rule_score"] = 0.6
    row["rule_observation"] = True
    row["rule_anomaly"] = True
    row["disease_rule_score"] = 0.0
    row["disease_rule_reasons"] = ""
    row["disease_rule_anomaly"] = False
    row["management_rule_score"] = 0.6
    row["management_rule_reasons"] = rule_id
    row["management_rule_anomaly"] = True
    row["environment_rule_score"] = 0.0
    row["environment_rule_reasons"] = ""
    row["environment_rule_anomaly"] = False
    row["model_anomaly"] = False
    row["final_alert"] = True
    row["rule_component"] = 0.0
    row["disease_score"] = row.get("model_component", 0.0)
    row["management_score"] = 0.6
    row["environment_score"] = 0.0
    row["management_alert"] = True
    row["environment_alert"] = False
    row["disease_alert"] = False
    row["alert_category"] = "management"
    row["disease_tier"] = "normal"
    row["primary_reason"] = f"rule: management: {rule_id}"
    return row


def _ensure_injection_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in TEXT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(object)
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
    for col in BOOLEAN_COLUMNS:
        if col not in df.columns:
            df[col] = False
    return df


def build_synthetic_management_rule_flags(source_flags: pd.DataFrame) -> pd.DataFrame:
    """Add feed_drop/water_drop examples to a final-ensemble-compatible flags table."""
    df = _ensure_injection_columns(source_flags)
    required = {"dataset_key", "chamber_number", "start_datetime", "end_datetime"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    normal = df[~df["final_alert"].astype(bool)].copy()
    if len(normal) < 2:
        raise ValueError("Need at least two non-alert rows to inject feed_drop and water_drop.")
    normal = normal.sort_values(["dataset_key", "chamber_number", "start_datetime"]).head(2)

    for source_index, rule_id in zip(normal.index, ["feed_drop", "water_drop"]):
        injected = _inject_management_alert(df.loc[source_index], rule_id)
        for col, value in injected.items():
            df.at[source_index, col] = value
    return df


def build_management_events(rule_flags: pd.DataFrame) -> pd.DataFrame:
    """Create synthetic events 20h after injected management alerts."""
    rows = []
    management = rule_flags[rule_flags["alert_category"].fillna("").astype(str).str.contains("management")]
    for idx, (_, row) in enumerate(management.sort_values("start_datetime").iterrows(), start=1):
        reason = str(row["management_rule_reasons"])
        start = pd.to_datetime(row["start_datetime"]) + pd.Timedelta(hours=20)
        event_type = "feed_drop" if "feed_drop" in reason else "water_drop"
        rows.append(
            {
                "event_id": f"synthetic-management-{idx:04d}",
                "farm_id": "synthetic-farm-a",
                "chamber_id": f"bioenergy:{row['dataset_key']}:{row['chamber_number']}",
                "event_type": event_type,
                "start_datetime": start,
                "end_datetime": start + pd.Timedelta(hours=8),
                "severity": 3,
                "vet_confirmed": True,
                "source": "synthetic_management_scenario",
                "notes": "synthetic management event generated from injected final alert row",
                "expected_rule": reason,
            }
        )
    return pd.DataFrame(rows)


def write_report(flags: pd.DataFrame, events: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    category_counts = flags["alert_category"].fillna("").replace("", "none").value_counts().reset_index()
    category_counts.columns = ["alert_category", "windows"]
    lines = [
        "# Synthetic Management Scenario 리포트",
        "",
        "## 목적",
        "",
        "`feed_drop`/`water_drop` management rule이 단위 검증을 넘어 final ensemble 테이블까지 올라오는지 확인한다.",
        "",
        "## Alert Category 분포",
        "",
        dataframe_to_markdown(category_counts),
        "",
        "## Synthetic Management Events",
        "",
        dataframe_to_markdown(events),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create synthetic management alert scenario artifacts.")
    parser.add_argument("--source-flags", default="artifacts/bioenergy_clean_baseline/bioenergy_rule_flags.csv")
    parser.add_argument("--output-dir", default="artifacts/synthetic_management_scenario")
    parser.add_argument("--events-output", default="data/raw/farm_events/synthetic_management_events.csv")
    parser.add_argument("--report", default="artifacts/synthetic_management_scenario_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = pd.read_csv(args.source_flags, low_memory=False)
    injected = build_synthetic_management_rule_flags(source)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    flags_path = output_dir / "bioenergy_rule_flags.csv"
    injected.to_csv(flags_path, index=False)

    events = build_management_events(injected)
    events_path = Path(args.events_output)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(events_path, index=False)

    report = write_report(injected, events, args.report)
    print(f"flags: {flags_path}")
    print(f"events: {events_path}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
