"""Build synthetic farm-event files for rule validation."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.domain_rules import build_window_raw_table, evaluate_rules, load_rules

EVENT_COLUMNS = [
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
    "expected_rule",
]


def _chamber_id(row: pd.Series) -> str:
    return f"bioenergy:{row['dataset_key']}:{row['chamber_number']}"


def _event_from_alert(row: pd.Series, event_id: str, event_type: str, expected_rule: str, lead_hours: int) -> dict:
    alert_start = pd.to_datetime(row["start_datetime"])
    event_start = alert_start + pd.Timedelta(hours=lead_hours)
    return {
        "event_id": event_id,
        "farm_id": "synthetic-farm-a",
        "chamber_id": _chamber_id(row),
        "event_type": event_type,
        "start_datetime": event_start,
        "end_datetime": event_start + pd.Timedelta(hours=8),
        "severity": 4 if event_type in {"fever", "environment_failure"} else 3,
        "vet_confirmed": True,
        "source": "synthetic_rule_validation",
        "notes": f"synthetic positive event generated from rule window: {row['rule_reasons']}",
        "expected_rule": expected_rule,
    }


def _event_without_alert(event_id: str, chamber_id: str, event_type: str, when: str, expected_rule: str) -> dict:
    start = pd.Timestamp(when)
    return {
        "event_id": event_id,
        "farm_id": "synthetic-farm-a",
        "chamber_id": chamber_id,
        "event_type": event_type,
        "start_datetime": start,
        "end_datetime": start + pd.Timedelta(hours=6),
        "severity": 2,
        "vet_confirmed": False,
        "source": "synthetic_rule_validation",
        "notes": "synthetic negative/control event; expected no lead-time match",
        "expected_rule": expected_rule,
    }


def _first_rule_hit(flags: pd.DataFrame, contains: list[str]) -> pd.Series:
    mask = pd.Series(True, index=flags.index)
    for rule_id in contains:
        mask = mask & flags["rule_reasons"].fillna("").str.contains(rule_id, regex=False)
    hits = flags[mask].sort_values("disease_score", ascending=False)
    if hits.empty:
        raise ValueError(f"No rule hit found for: {contains}")
    return hits.iloc[0]


def build_synthetic_event_sets(rule_flags: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Create positive, negative, and mixed synthetic event sets."""
    fever_row = _first_rule_hit(rule_flags, ["rectal_temp_high"])
    fever_env_row = _first_rule_hit(rule_flags, ["rectal_temp_high", "co2_high"])
    environment_row = _first_rule_hit(rule_flags, ["co2_high", "nh3_high"])

    positives = pd.DataFrame(
        [
            _event_from_alert(fever_row, "synthetic-positive-0001", "fever", "rectal_temp_high", lead_hours=20),
            _event_from_alert(
                fever_env_row,
                "synthetic-positive-0002",
                "respiratory",
                "rectal_temp_high+co2_high",
                lead_hours=20,
            ),
            _event_from_alert(
                environment_row,
                "synthetic-positive-0003",
                "environment_failure",
                "co2_high+nh3_high",
                lead_hours=20,
            ),
        ],
        columns=EVENT_COLUMNS,
    )

    negatives = pd.DataFrame(
        [
            _event_without_alert(
                "synthetic-negative-0001",
                "bioenergy:71763:2",
                "feed_drop",
                "2023-08-20 08:00:00",
                "feed_drop",
            ),
            _event_without_alert(
                "synthetic-negative-0002",
                "activity622:facility3:pen6",
                "water_drop",
                "2021-08-23 00:00:00",
                "water_drop",
            ),
            _event_without_alert(
                "synthetic-negative-0003",
                "bioenergy:71763:3",
                "treatment",
                "2023-09-20 08:00:00",
                "none",
            ),
        ],
        columns=EVENT_COLUMNS,
    )

    mixed = pd.concat([positives, negatives], ignore_index=True)
    return {
        "synthetic_rule_positive_events.csv": positives,
        "synthetic_rule_negative_events.csv": negatives,
        "synthetic_mixed_events.csv": mixed,
    }


def build_injection_cases(artifact_dir: str | Path, rules_path: str | Path, seq_len: int = 24) -> pd.DataFrame:
    """Inject no-hit management/environment values into one window and verify rules fire."""
    window_table, _, _ = build_window_raw_table(artifact_dir, seq_len=seq_len)
    rules = load_rules(rules_path)["rules"]
    base = window_table.iloc[[0]].copy()
    neutral_values = {
        "feedstuff_volume_mean_zscore_3d__wmean": 0.0,
        "watersupply_mean_zscore_3d__wmean": 0.0,
        "ventilation_rate_mean__wmean": 2.5,
        "CO2_mean__wmax": 800.0,
        "NH3_mean__wmax": 8.0,
        "rectal_temperature_mean_corrected__wmax": 38.5,
        "neck_temperature_mean__wmax": 37.0,
        "T_mean__wmax": 26.0,
    }
    for col, value in neutral_values.items():
        if col in base.columns:
            base[col] = value

    cases = []
    injections = {
        "feed_drop": {"feedstuff_volume_mean_zscore_3d__wmean": -2.0},
        "water_drop": {"watersupply_mean_zscore_3d__wmean": -2.0},
        "ventilation_low": {"ventilation_rate_mean__wmean": 1.0},
        "ventilation_low_with_co2_high": {"ventilation_rate_mean__wmean": 1.0, "CO2_mean__wmax": 1000.0},
        "ventilation_low_with_nh3_high": {"ventilation_rate_mean__wmean": 1.0, "NH3_mean__wmax": 10.0},
    }

    for rule_id, updates in injections.items():
        injected = base.copy()
        for col, value in updates.items():
            injected[col] = value
        result = evaluate_rules(injected, rules)
        rule_col = f"rule_{rule_id}"
        cases.append(
            {
                "case": rule_id,
                "expected_rule": rule_id,
                "rule_fired": bool(result.iloc[0][rule_col]),
                "rule_anomaly": bool(result.iloc[0]["rule_anomaly"]),
                "disease_rule_anomaly": bool(result.iloc[0]["disease_rule_anomaly"]),
                "management_rule_anomaly": bool(result.iloc[0]["management_rule_anomaly"]),
                "environment_rule_anomaly": bool(result.iloc[0]["environment_rule_anomaly"]),
                "rule_score": float(result.iloc[0]["rule_score"]),
                "disease_rule_score": float(result.iloc[0]["disease_rule_score"]),
                "management_rule_score": float(result.iloc[0]["management_rule_score"]),
                "environment_rule_score": float(result.iloc[0]["environment_rule_score"]),
                "rule_reasons": result.iloc[0]["rule_reasons"],
            }
        )
    return pd.DataFrame(cases)


def write_report(event_paths: dict[str, Path], injection: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    file_rows = [{"file": str(path), "rows": sum(1 for _ in path.open(encoding="utf-8")) - 1} for path in event_paths.values()]
    lines = [
        "# Synthetic Rule Event 생성 리포트",
        "",
        "## 생성 파일",
        "",
        dataframe_to_markdown(pd.DataFrame(file_rows)),
        "",
        "## Injection 규칙 검증",
        "",
        dataframe_to_markdown(injection),
        "",
        "## 해석",
        "",
        "- positive 파일은 현재 실제 rule hit window 근처에 이벤트를 배치해 lead-time recall이 올라가야 한다.",
        "- negative 파일은 경보가 없는 chamber/time을 골라 불필요한 match가 낮게 유지되어야 한다.",
        "- feed/water/ventilation 계열은 현재 실제 validation window hit가 없으므로 injection으로 rule logic만 먼저 검증한다.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create synthetic farm-event files for rule validation.")
    parser.add_argument("--rule-flags", default="artifacts/bioenergy_clean_baseline/bioenergy_rule_flags.csv")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--rules", default="config/domain_rules.json")
    parser.add_argument("--output-dir", default="data/raw/farm_events")
    parser.add_argument("--injection-output", default="artifacts/synthetic_rule_injection_checks.csv")
    parser.add_argument("--report", default="artifacts/synthetic_rule_events_report.md")
    parser.add_argument("--seq-len", type=int, default=24)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rule_flags = pd.read_csv(args.rule_flags, low_memory=False)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    event_sets = build_synthetic_event_sets(rule_flags)
    paths = {}
    for filename, df in event_sets.items():
        path = output_dir / filename
        df.to_csv(path, index=False)
        paths[filename] = path

    injection = build_injection_cases(args.artifact_dir, args.rules, seq_len=args.seq_len)
    injection_path = Path(args.injection_output)
    injection_path.parent.mkdir(parents=True, exist_ok=True)
    injection.to_csv(injection_path, index=False)

    report = write_report(paths, injection, args.report)
    for name, path in paths.items():
        print(f"{name}: {path}")
    print(f"injection: {injection_path}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
