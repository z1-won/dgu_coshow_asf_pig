"""Knowledge-based rule layer, run alongside (not mixed into) the LSTM Autoencoder.

See docs/DOMAIN_RULE_GUIDANCE.md for why rules are kept separate from model
training: a wrong rule threshold would otherwise silently bias what the model
learns as "normal", and mixing the two makes it impossible to explain which
kind of signal triggered an alert.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown


def load_rules(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "rectal_temperature_mean": (35.0, 42.0),
    "back_temperature_mean": (25.0, 42.0),
    "neck_temperature_mean": (25.0, 42.0),
    "head_temperature_mean": (25.0, 42.0),
    "T_mean": (-10.0, 45.0),
}


def filter_implausible_values(
    df: pd.DataFrame, ranges: dict[str, tuple[float, float]] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mask sensor readings outside a physiologically/environmentally plausible range.

    Dataset 71408's rectal_temperature_mean swings from 32.3C to 41.3C within a
    single day at points -- that isn't real pig physiology, it's sensor noise, and
    a naive threshold rule would flag it as fever. Implausible raw readings are
    masked to NaN before any window mean/max is computed, so rules only ever see
    physically plausible values. Returns the masked dataframe plus a summary of how
    many readings were dropped per feature (report this -- don't silently discard).
    """
    ranges = ranges or PLAUSIBLE_RANGES
    df = df.copy()
    summary_rows = []
    for col, (low, high) in ranges.items():
        if col not in df.columns:
            continue
        present = df[col].notna()
        implausible = present & ((df[col] < low) | (df[col] > high))
        summary_rows.append(
            {
                "feature": col,
                "plausible_range": f"[{low}, {high}]",
                "filtered_rows": int(implausible.sum()),
                "total_present_rows": int(present.sum()),
            }
        )
        df.loc[implausible, col] = np.nan
    return df, pd.DataFrame(summary_rows)


def build_window_raw_table(artifact_dir: str | Path, seq_len: int = 24) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-window mean/max of the *raw* (unscaled) validation features.

    Rule thresholds are physical values (e.g. 40.5 degrees C), so they must be
    checked against raw sensor readings, not the per-chamber scaled values the
    model trains on. This mirrors bioenergy_report.load_window_metadata's
    windowing exactly, but pulls values from bioenergy_aggregated.csv (raw)
    for the same val-split rows instead of building a model input array.
    """
    artifacts = Path(artifact_dir)
    val_scaled = pd.read_csv(artifacts / "bioenergy_val_scaled.csv", low_memory=False)
    aggregated = pd.read_csv(artifacts / "bioenergy_aggregated.csv", low_memory=False)

    for df in (val_scaled, aggregated):
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    val_raw = val_scaled[["dataset_key", "chamber_number", "datetime"]].merge(
        aggregated,
        on=["dataset_key", "chamber_number", "datetime"],
        how="left",
    )
    val_raw, quality_summary = filter_implausible_values(val_raw)

    feature_columns = [
        col
        for col in val_raw.columns
        if col not in {"dataset_key", "chamber_number", "datetime"}
        and pd.api.types.is_numeric_dtype(val_raw[col])
    ]

    rows = []
    for (dataset_key, chamber_number), group in val_raw.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime").reset_index(drop=True)
        for start in range(len(group) - seq_len + 1):
            end = start + seq_len - 1
            window = group.iloc[start : end + 1]
            row = {
                "dataset_key": dataset_key,
                "chamber_number": chamber_number,
                "start_datetime": group.loc[start, "datetime"],
                "end_datetime": group.loc[end, "datetime"],
                "window_start_index": start,
                "window_end_index": end,
            }
            for col in feature_columns:
                row[f"{col}__wmean"] = window[col].mean()
                row[f"{col}__wmax"] = window[col].max()
            rows.append(row)
    return pd.DataFrame(rows), quality_summary


def evaluate_rules(window_table: pd.DataFrame, rules: list[dict]) -> pd.DataFrame:
    result = window_table[
        ["dataset_key", "chamber_number", "start_datetime", "end_datetime"]
    ].copy()
    reasons = [[] for _ in range(len(result))]
    triggered_any = np.zeros(len(result), dtype=bool)

    for rule in rules:
        agg = rule.get("agg", "mean")
        column = f"{rule['feature']}__w{agg}"
        if column not in window_table.columns:
            raise KeyError(
                f"Rule '{rule['id']}' references unknown feature '{rule['feature']}' "
                f"(looked for column '{column}')."
            )
        values = window_table[column]
        op = rule["op"]
        if op == ">=":
            hit = (values >= rule["threshold"]).to_numpy()
        elif op == "<=":
            hit = (values <= rule["threshold"]).to_numpy()
        else:
            raise ValueError(f"Unsupported operator '{op}' in rule '{rule['id']}'.")

        result[f"rule_{rule['id']}"] = hit
        triggered_any = triggered_any | hit
        for idx in np.flatnonzero(hit):
            reasons[idx].append(rule["id"])

    result["rule_anomaly"] = triggered_any
    result["rule_reasons"] = [",".join(r) for r in reasons]
    return result


def combine_with_model(rule_table: pd.DataFrame, detection_windows: pd.DataFrame) -> pd.DataFrame:
    detection = detection_windows.copy()
    detection["start_datetime"] = pd.to_datetime(detection["start_datetime"], errors="coerce")
    detection["end_datetime"] = pd.to_datetime(detection["end_datetime"], errors="coerce")

    combined = rule_table.merge(
        detection[
            ["dataset_key", "chamber_number", "start_datetime", "end_datetime", "reconstruction_error", "raw_anomaly", "confirmed_anomaly"]
        ],
        on=["dataset_key", "chamber_number", "start_datetime", "end_datetime"],
        how="left",
    )
    combined["model_anomaly"] = combined["confirmed_anomaly"].fillna(False)
    combined["final_alert"] = combined["model_anomaly"] | combined["rule_anomaly"]

    def primary_reason(row: pd.Series) -> str:
        parts = []
        if row["model_anomaly"]:
            parts.append("model reconstruction error threshold 초과")
        if row["rule_anomaly"]:
            parts.append(f"rule: {row['rule_reasons']}")
        return " + ".join(parts) if parts else ""

    combined["primary_reason"] = combined.apply(primary_reason, axis=1)
    return combined.sort_values(["final_alert", "model_anomaly", "rule_anomaly"], ascending=False).reset_index(drop=True)


def write_combined_report(
    combined: pd.DataFrame, output_path: str | Path, quality_summary: pd.DataFrame | None = None
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    alerts = combined[combined["final_alert"]]
    cols = [
        "dataset_key",
        "chamber_number",
        "start_datetime",
        "end_datetime",
        "model_anomaly",
        "rule_anomaly",
        "primary_reason",
    ]
    lines = [
        "# 모델 + 규칙 결합 경보 리포트",
        "",
        f"- 전체 검증 window: `{len(combined)}`",
        f"- model anomaly (confirmed): `{int(combined['model_anomaly'].sum())}`",
        f"- rule anomaly: `{int(combined['rule_anomaly'].sum())}`",
        f"- 최종 경보(model OR rule): `{int(combined['final_alert'].sum())}`",
        "",
    ]
    if quality_summary is not None and quality_summary["filtered_rows"].sum() > 0:
        filtered = quality_summary[quality_summary["filtered_rows"] > 0]
        lines += [
            "## 센서 타당성 필터링 (규칙 적용 전 제외된 값)",
            "",
            "아래 컬럼에서 생리적/환경적으로 타당하지 않은 값(예: 직장체온 32.3도)은 규칙 판정에서 제외했습니다.",
            "",
            dataframe_to_markdown(filtered),
            "",
        ]
    lines += [
        "## 경보 목록",
        "",
        dataframe_to_markdown(alerts[cols]) if len(alerts) else "경보 없음.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def apply_rules(
    artifact_dir: str | Path,
    rules_path: str | Path,
    seq_len: int = 24,
) -> dict[str, Path]:
    artifacts = Path(artifact_dir)
    config = load_rules(rules_path)

    window_table, quality_summary = build_window_raw_table(artifacts, seq_len=seq_len)
    rule_table = evaluate_rules(window_table, config["rules"])

    detection_windows = pd.read_csv(artifacts / "bioenergy_detection_windows.csv", low_memory=False)
    combined = combine_with_model(rule_table, detection_windows)

    flags_path = artifacts / "bioenergy_rule_flags.csv"
    report_path = artifacts / "bioenergy_combined_alert_report.md"
    quality_path = artifacts / "bioenergy_sensor_quality_summary.csv"
    combined.to_csv(flags_path, index=False)
    quality_summary.to_csv(quality_path, index=False)
    write_combined_report(combined, report_path, quality_summary)
    return {"flags": flags_path, "report": report_path, "sensor_quality": quality_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the domain rule layer and combine with model anomaly flags.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--rules", default="config/domain_rules.json")
    parser.add_argument("--seq-len", type=int, default=24)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = apply_rules(args.artifact_dir, args.rules, seq_len=args.seq_len)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
