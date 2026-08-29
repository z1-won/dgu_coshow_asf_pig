"""Compare baseline domain rules against the upgraded management/environment rules."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.domain_rules import (
    build_window_raw_table,
    combine_with_model,
    evaluate_rules,
    load_rules,
)
from pigproject.farm_event_schema import (
    DEFAULT_LEAD_TIME_HOURS,
    evaluate_lead_time,
    summarize_lead_time,
)

BASELINE_RULE_IDS = {
    "rectal_temp_high",
    "neck_temp_high",
    "barn_temp_high",
    "feed_drop",
    "water_spike",
}


def _window_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["dataset_key"].astype(str)
        + "|"
        + df["chamber_number"].astype(str)
        + "|"
        + pd.to_datetime(df["start_datetime"], errors="coerce").astype(str)
        + "|"
        + pd.to_datetime(df["end_datetime"], errors="coerce").astype(str)
    )


def _evaluate_rule_set(
    artifact_dir: str | Path,
    rules: list[dict],
    seq_len: int,
) -> pd.DataFrame:
    window_table, _, _ = build_window_raw_table(artifact_dir, seq_len=seq_len)
    rule_table = evaluate_rules(window_table, rules)
    detection_windows = pd.read_csv(Path(artifact_dir) / "bioenergy_detection_windows.csv", low_memory=False)
    return combine_with_model(rule_table, detection_windows)


def _standardize_for_final_alerts(bioenergy: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track": "bioenergy",
            "chamber_id": "bioenergy:" + bioenergy["dataset_key"].astype(str) + ":" + bioenergy["chamber_number"].astype(str),
            "start_datetime": bioenergy["start_datetime"],
            "end_datetime": bioenergy["end_datetime"],
            "track_score": bioenergy["disease_score"],
            "tier": bioenergy["disease_tier"],
            "reason": bioenergy["primary_reason"],
            "final_alert": bioenergy["final_alert"],
        }
    )


def summarize_rule_result(name: str, df: pd.DataFrame) -> dict:
    tier_counts = df["disease_tier"].value_counts()
    return {
        "rule_set": name,
        "windows": len(df),
        "rule_observation": int(df["rule_observation"].sum()) if "rule_observation" in df.columns else pd.NA,
        "rule_anomaly": int(df["rule_anomaly"].sum()),
        "final_alert": int(df["final_alert"].sum()),
        "disease_alert": int(df["disease_alert"].sum()) if "disease_alert" in df.columns else pd.NA,
        "management_alert": int(df["management_alert"].sum()) if "management_alert" in df.columns else pd.NA,
        "environment_alert": int(df["environment_alert"].sum()) if "environment_alert" in df.columns else pd.NA,
        "high_tier": int(tier_counts.get("high", 0)),
        "medium_tier": int(tier_counts.get("medium", 0)),
        "normal_tier": int(tier_counts.get("normal", 0)),
        "mean_disease_score": float(df["disease_score"].mean()),
        "max_disease_score": float(df["disease_score"].max()),
    }


def compare_rule_sets(
    artifact_dir: str | Path,
    rules_path: str | Path,
    events_path: str | Path | None = None,
    seq_len: int = 24,
    horizons_hours: tuple[int, ...] = DEFAULT_LEAD_TIME_HOURS,
) -> dict[str, pd.DataFrame]:
    config = load_rules(rules_path)
    upgraded_rules = config["rules"]
    baseline_rules = [rule for rule in upgraded_rules if rule["id"] in BASELINE_RULE_IDS]

    baseline = _evaluate_rule_set(artifact_dir, baseline_rules, seq_len=seq_len)
    upgraded = _evaluate_rule_set(artifact_dir, upgraded_rules, seq_len=seq_len)

    baseline_keys = set(_window_key(baseline[baseline["final_alert"]]))
    upgraded_alerts = upgraded[upgraded["final_alert"]].copy()
    upgraded_alerts["_window_key"] = _window_key(upgraded_alerts)
    new_alerts = upgraded_alerts[~upgraded_alerts["_window_key"].isin(baseline_keys)].drop(columns=["_window_key"])

    summary = pd.DataFrame(
        [
            summarize_rule_result("baseline_rules", baseline),
            summarize_rule_result("upgraded_rules", upgraded),
        ]
    )

    reason_compare = pd.concat(
        [
            baseline[baseline["final_alert"]]["primary_reason"].value_counts().rename("baseline_alerts"),
            upgraded[upgraded["final_alert"]]["primary_reason"].value_counts().rename("upgraded_alerts"),
        ],
        axis=1,
    ).fillna(0).astype(int).reset_index(names="primary_reason")

    lead_metrics = pd.DataFrame()
    if events_path and Path(events_path).exists():
        events = pd.read_csv(events_path, low_memory=False)
        for col in ["start_datetime", "end_datetime"]:
            events[col] = pd.to_datetime(events[col], errors="coerce")
        metric_frames = []
        for rule_set_name, df in [("baseline_rules", baseline), ("upgraded_rules", upgraded)]:
            alerts = _standardize_for_final_alerts(df)
            lead_matches, lead_event_summary = evaluate_lead_time(events, alerts, horizons_hours)
            metrics = summarize_lead_time(lead_event_summary, lead_matches, alerts, horizons_hours)
            metrics.insert(0, "rule_set", rule_set_name)
            metric_frames.append(metrics)
        lead_metrics = pd.concat(metric_frames, ignore_index=True)

    return {
        "summary": summary,
        "reason_compare": reason_compare,
        "new_alerts": new_alerts,
        "baseline": baseline,
        "upgraded": upgraded,
        "lead_metrics": lead_metrics,
    }


def write_report(results: dict[str, pd.DataFrame], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    new_alert_cols = [
        "dataset_key",
        "chamber_number",
        "start_datetime",
        "end_datetime",
        "disease_score",
        "management_score",
        "environment_score",
        "alert_category",
        "disease_tier",
        "rule_reasons",
        "primary_reason",
    ]
    lines = [
        "# 규칙 추가 전/후 비교 리포트",
        "",
        "## 비교 기준",
        "",
        "- baseline: 기존 온도 중심 규칙 + 기존 feed/water spike 규칙",
        "- upgraded: baseline + water drop + ventilation + CO2/NH3 + 환기/공기질 복합 규칙",
        "- low severity 단독 신호는 `rule_observation`으로 기록하고, `rule_score >= 0.8`부터 `rule_anomaly`로 승격",
        "",
        "## 전체 지표",
        "",
        dataframe_to_markdown(results["summary"]),
        "",
        "## 경보 이유별 변화",
        "",
        dataframe_to_markdown(results["reason_compare"]),
        "",
        "## 새로 추가된 최종 경보 Window",
        "",
        dataframe_to_markdown(results["new_alerts"][new_alert_cols]) if len(results["new_alerts"]) else "새 경보 없음.",
    ]
    if len(results["lead_metrics"]):
        lines += [
            "",
            "## Lead-Time 지표 변화",
            "",
            dataframe_to_markdown(results["lead_metrics"]),
        ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare baseline and upgraded domain rule sets.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--rules", default="config/domain_rules.json")
    parser.add_argument("--events", default="data/raw/farm_events/farm_event_log.csv")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--lead-hours", default="24,48,72")
    parser.add_argument("--summary-output", default="artifacts/rule_upgrade_compare_summary.csv")
    parser.add_argument("--new-alerts-output", default="artifacts/rule_upgrade_new_alerts.csv")
    parser.add_argument("--reason-output", default="artifacts/rule_upgrade_reason_compare.csv")
    parser.add_argument("--lead-output", default="artifacts/rule_upgrade_lead_time_compare.csv")
    parser.add_argument("--report", default="artifacts/rule_upgrade_compare_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    horizons_hours = tuple(int(value.strip()) for value in args.lead_hours.split(",") if value.strip())
    results = compare_rule_sets(
        artifact_dir=args.artifact_dir,
        rules_path=args.rules,
        events_path=args.events,
        seq_len=args.seq_len,
        horizons_hours=horizons_hours,
    )

    outputs = {
        "summary": Path(args.summary_output),
        "new_alerts": Path(args.new_alerts_output),
        "reasons": Path(args.reason_output),
        "lead": Path(args.lead_output),
    }
    outputs["summary"].parent.mkdir(parents=True, exist_ok=True)
    results["summary"].to_csv(outputs["summary"], index=False)
    results["new_alerts"].to_csv(outputs["new_alerts"], index=False)
    results["reason_compare"].to_csv(outputs["reasons"], index=False)
    results["lead_metrics"].to_csv(outputs["lead"], index=False)
    report = write_report(results, args.report)

    for name, path in outputs.items():
        print(f"{name}: {path}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
