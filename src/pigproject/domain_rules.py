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


SEVERITY_WEIGHTS: dict[str, float] = {"high": 1.0, "medium": 0.6, "low": 0.3}
CO_OCCURRENCE_BONUS_PER_EXTRA_RULE = 0.3
MODEL_COMPONENT_WEIGHT = 0.5
MODEL_COMPONENT_CAP = 2.0
DISEASE_TIER_THRESHOLDS: dict[str, float] = {"high": 1.5, "medium": 0.8}
RISK_CATEGORY_THRESHOLDS: dict[str, float] = {"disease": 0.8, "management": 0.6, "environment": 0.8}
RISK_CATEGORIES = ("disease", "management", "environment")


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


REFERENCE_BARN_TEMP = 26.0


def fit_barn_temp_correction(
    df: pd.DataFrame,
    temp_col: str = "rectal_temperature_mean",
    barn_col: str = "T_mean",
    reference_barn_temp: float = REFERENCE_BARN_TEMP,
) -> dict[str, float]:
    """Fit rectal_corrected = observed - slope * (barn_temp - reference).

    Same regression as docs/TEMPERATURE_ONLY_BASELINE_REPORT.md's correction
    work, refit here on whatever data is currently in the artifact dir (that
    report's numbers predate the per-pig aggregation fix and are marked
    stale). Ambient barn temperature is a confound for a raw fever threshold
    -- a hot barn on a hot day can push rectal temperature up without the
    animal being sick, so the rule should react to the deviation left over
    after removing that environmental effect, not the raw reading.
    """
    pairs = df[[temp_col, barn_col]].dropna()
    if len(pairs) < 10:
        return {"slope": 0.0, "intercept": float(pairs[temp_col].mean()) if len(pairs) else 0.0, "reference_barn_temp": reference_barn_temp, "pearson_corr": 0.0, "n_rows": len(pairs)}
    slope, intercept = np.polyfit(pairs[barn_col], pairs[temp_col], deg=1)
    corr = float(np.corrcoef(pairs[barn_col], pairs[temp_col])[0, 1]) if pairs[barn_col].std() > 0 else 0.0
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "reference_barn_temp": reference_barn_temp,
        "pearson_corr": corr,
        "n_rows": len(pairs),
    }


def apply_barn_temp_correction(
    df: pd.DataFrame, correction: dict[str, float], temp_col: str = "rectal_temperature_mean", barn_col: str = "T_mean"
) -> pd.Series:
    return df[temp_col] - correction["slope"] * (df[barn_col] - correction["reference_barn_temp"])


def build_window_raw_table(
    artifact_dir: str | Path, seq_len: int = 24
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
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

    aggregated_filtered, _ = filter_implausible_values(aggregated)
    correction = {}
    if "rectal_temperature_mean" in aggregated_filtered.columns and "T_mean" in aggregated_filtered.columns:
        correction = fit_barn_temp_correction(aggregated_filtered)

    val_raw = val_scaled[["dataset_key", "chamber_number", "datetime"]].merge(
        aggregated,
        on=["dataset_key", "chamber_number", "datetime"],
        how="left",
    )
    val_raw, quality_summary = filter_implausible_values(val_raw)

    if correction:
        val_raw["rectal_temperature_mean_corrected"] = apply_barn_temp_correction(val_raw, correction)

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
                row[f"{col}__wmin"] = window[col].min()
            rows.append(row)
    return pd.DataFrame(rows), quality_summary, correction


def evaluate_rules(window_table: pd.DataFrame, rules: list[dict]) -> pd.DataFrame:
    """Evaluate each rule and fold hits into a co-occurrence-weighted rule_score.

    A plain OR treats "just ran a fever" the same as "fever AND stopped eating
    AND drank more than usual at the same time" -- but a real ASF read (per the
    team's symptom research in 베어메모) is that concurrent symptoms are far
    more disease-specific than any single one. rule_score sums each triggered
    rule's severity weight, then adds a flat bonus per additional rule beyond
    the first that fires on the same window, so co-occurring symptoms score
    disproportionately higher than the same rules firing on separate windows.
    """
    result = window_table[
        ["dataset_key", "chamber_number", "start_datetime", "end_datetime"]
    ].copy()
    reasons = [[] for _ in range(len(result))]
    reasons_by_category = {category: [[] for _ in range(len(result))] for category in RISK_CATEGORIES}
    triggered_any = np.zeros(len(result), dtype=bool)
    severity_sum = np.zeros(len(result), dtype=float)
    triggered_count = np.zeros(len(result), dtype=int)
    category_scores = {category: np.zeros(len(result), dtype=float) for category in RISK_CATEGORIES}
    category_counts = {category: np.zeros(len(result), dtype=int) for category in RISK_CATEGORIES}

    def evaluate_single_condition(rule: dict) -> np.ndarray:
        agg = rule.get("agg", "mean")
        if agg not in {"mean", "max", "min"}:
            raise ValueError(f"Unsupported aggregation '{agg}' in rule '{rule['id']}'.")
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
        return hit

    for rule in rules:
        if "all_of" in rule:
            condition_hits = [evaluate_single_condition({**condition, "id": rule["id"]}) for condition in rule["all_of"]]
            hit = np.logical_and.reduce(condition_hits)
        else:
            hit = evaluate_single_condition(rule)

        weight = SEVERITY_WEIGHTS.get(rule.get("severity", "medium"), SEVERITY_WEIGHTS["medium"])
        category = rule.get("category", "disease")
        if category not in category_scores:
            category = "disease"
        result[f"rule_{rule['id']}"] = hit
        triggered_any = triggered_any | hit
        severity_sum = severity_sum + np.where(hit, weight, 0.0)
        triggered_count = triggered_count + hit.astype(int)
        category_scores[category] = category_scores[category] + np.where(hit, weight, 0.0)
        category_counts[category] = category_counts[category] + hit.astype(int)
        for idx in np.flatnonzero(hit):
            reasons[idx].append(rule["id"])
            reasons_by_category[category][idx].append(rule["id"])

    co_occurrence_bonus = CO_OCCURRENCE_BONUS_PER_EXTRA_RULE * np.maximum(0, triggered_count - 1)

    result["rule_reasons"] = [",".join(r) for r in reasons]
    result["rule_triggered_count"] = triggered_count
    result["rule_severity_sum"] = severity_sum
    result["rule_co_occurrence_bonus"] = co_occurrence_bonus
    result["rule_score"] = severity_sum + co_occurrence_bonus
    for category in RISK_CATEGORIES:
        category_bonus = CO_OCCURRENCE_BONUS_PER_EXTRA_RULE * np.maximum(0, category_counts[category] - 1)
        result[f"{category}_rule_score"] = category_scores[category] + category_bonus
        result[f"{category}_rule_reasons"] = [",".join(r) for r in reasons_by_category[category]]
        result[f"{category}_rule_anomaly"] = result[f"{category}_rule_score"] >= RISK_CATEGORY_THRESHOLDS[category]
    result["rule_observation"] = triggered_any
    result["rule_anomaly"] = (
        result["disease_rule_anomaly"] | result["management_rule_anomaly"] | result["environment_rule_anomaly"]
    )
    return result


def disease_tier_for(score: float) -> str:
    if score >= DISEASE_TIER_THRESHOLDS["high"]:
        return "high"
    if score >= DISEASE_TIER_THRESHOLDS["medium"]:
        return "medium"
    return "normal"


def combine_with_model(rule_table: pd.DataFrame, detection_windows: pd.DataFrame) -> pd.DataFrame:
    detection = detection_windows.copy()
    detection["start_datetime"] = pd.to_datetime(detection["start_datetime"], errors="coerce")
    detection["end_datetime"] = pd.to_datetime(detection["end_datetime"], errors="coerce")

    combined = rule_table.merge(
        detection[
            [
                "dataset_key",
                "chamber_number",
                "start_datetime",
                "end_datetime",
                "reconstruction_error",
                "threshold",
                "raw_anomaly",
                "confirmed_anomaly",
            ]
        ],
        on=["dataset_key", "chamber_number", "start_datetime", "end_datetime"],
        how="left",
    )
    combined["model_anomaly"] = combined["confirmed_anomaly"].fillna(False)
    combined["final_alert"] = combined["model_anomaly"] | combined["rule_anomaly"]

    # Disease score: model_component reflects how far past its own threshold the
    # reconstruction error sits (capped so one wildly large error can't drown out
    # everything else); rule_component already carries the co-occurrence bonus
    # from evaluate_rules(). See docs/ASF_DISEASE_SCORE.md for the rationale and
    # tier cutoffs.
    ratio = (combined["reconstruction_error"] / combined["threshold"]).clip(upper=MODEL_COMPONENT_CAP)
    combined["model_component"] = (MODEL_COMPONENT_WEIGHT * ratio).fillna(0.0)
    combined["rule_component"] = combined["disease_rule_score"]
    combined["disease_score"] = combined["model_component"] + combined["rule_component"]
    combined["disease_tier"] = combined["disease_score"].apply(disease_tier_for)
    combined["management_score"] = combined["management_rule_score"]
    combined["environment_score"] = combined["environment_rule_score"]
    combined["management_alert"] = combined["management_rule_anomaly"]
    combined["environment_alert"] = combined["environment_rule_anomaly"]
    combined["disease_alert"] = combined["model_anomaly"] | combined["disease_rule_anomaly"]

    def alert_category(row: pd.Series) -> str:
        categories = []
        if row["disease_alert"]:
            categories.append("disease")
        if row["management_alert"]:
            categories.append("management")
        if row["environment_alert"]:
            categories.append("environment")
        return ",".join(categories)

    combined["alert_category"] = combined.apply(alert_category, axis=1)

    def primary_reason(row: pd.Series) -> str:
        parts = []
        if row["model_anomaly"]:
            parts.append("model reconstruction error threshold 초과")
        if row["rule_anomaly"]:
            category_reasons = []
            for category in RISK_CATEGORIES:
                value = row.get(f"{category}_rule_reasons", "")
                if value:
                    category_reasons.append(f"{category}: {value}")
            parts.append("rule: " + " | ".join(category_reasons))
        return " + ".join(parts) if parts else ""

    combined["primary_reason"] = combined.apply(primary_reason, axis=1)
    return combined.sort_values("disease_score", ascending=False).reset_index(drop=True)


def write_combined_report(
    combined: pd.DataFrame,
    output_path: str | Path,
    quality_summary: pd.DataFrame | None = None,
    correction: dict[str, float] | None = None,
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
        "alert_category",
        "disease_score",
        "management_score",
        "environment_score",
        "disease_tier",
        "primary_reason",
    ]
    tier_counts = combined["disease_tier"].value_counts()
    high_tier = combined[combined["disease_tier"] == "high"]
    lines = [
        "# 모델 + 규칙 결합 경보 리포트",
        "",
        f"- 전체 검증 window: `{len(combined)}`",
        f"- model anomaly (confirmed): `{int(combined['model_anomaly'].sum())}`",
        f"- rule anomaly: `{int(combined['rule_anomaly'].sum())}`",
        f"- disease alert: `{int(combined['disease_alert'].sum())}`",
        f"- management alert: `{int(combined['management_alert'].sum())}`",
        f"- environment alert: `{int(combined['environment_alert'].sum())}`",
        f"- 최종 경보(model OR rule): `{int(combined['final_alert'].sum())}`",
        "",
        "## Disease Score 분포",
        "",
        f"- high (>= {DISEASE_TIER_THRESHOLDS['high']}): `{int(tier_counts.get('high', 0))}`",
        f"- medium (>= {DISEASE_TIER_THRESHOLDS['medium']}): `{int(tier_counts.get('medium', 0))}`",
        f"- normal: `{int(tier_counts.get('normal', 0))}`",
        "",
    ]
    category_summary = pd.DataFrame(
        [
            {
                "category": "disease",
                "alerts": int(combined["disease_alert"].sum()),
                "mean_score": combined["disease_score"].mean(),
                "max_score": combined["disease_score"].max(),
            },
            {
                "category": "management",
                "alerts": int(combined["management_alert"].sum()),
                "mean_score": combined["management_score"].mean(),
                "max_score": combined["management_score"].max(),
            },
            {
                "category": "environment",
                "alerts": int(combined["environment_alert"].sum()),
                "mean_score": combined["environment_score"].mean(),
                "max_score": combined["environment_score"].max(),
            },
        ]
    )
    lines += [
        "## Risk Category별 요약",
        "",
        dataframe_to_markdown(category_summary),
        "",
    ]
    if correction:
        lines += [
            "## 돈사온도 보정 적용",
            "",
            f"`rectal_corrected = rectal_observed - ({correction['slope']:.6f} * (T_mean - {correction['reference_barn_temp']:.3f}))`",
            "",
            f"- 회귀에 쓴 행 수: `{correction['n_rows']}`",
            f"- Pearson 상관계수: `{correction['pearson_corr']:.4f}`"
            + (" (거의 0에 가까움 -- 이 데이터에서는 돈사온도와 직장체온의 선형관계가 약해서 보정 효과가 작다)" if abs(correction["pearson_corr"]) < 0.1 else ""),
            f"- `rectal_temp_high` 규칙은 원본이 아니라 이 보정값(`rectal_temperature_mean_corrected`)에 적용된다.",
            "",
        ]
    if len(high_tier):
        lines += [
            "### disease_tier == high 인 window (증상 동시발생 포함)",
            "",
            dataframe_to_markdown(
                high_tier[
                    [
                        "dataset_key",
                        "chamber_number",
                        "start_datetime",
                        "end_datetime",
                        "model_component",
                        "rule_component",
                        "disease_score",
                        "rule_reasons",
                    ]
                ]
            ),
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

    window_table, quality_summary, correction = build_window_raw_table(artifacts, seq_len=seq_len)
    rule_table = evaluate_rules(window_table, config["rules"])

    detection_windows = pd.read_csv(artifacts / "bioenergy_detection_windows.csv", low_memory=False)
    combined = combine_with_model(rule_table, detection_windows)

    flags_path = artifacts / "bioenergy_rule_flags.csv"
    report_path = artifacts / "bioenergy_combined_alert_report.md"
    quality_path = artifacts / "bioenergy_sensor_quality_summary.csv"
    correction_path = artifacts / "bioenergy_temp_correction_formula.csv"
    combined.to_csv(flags_path, index=False)
    quality_summary.to_csv(quality_path, index=False)
    if correction:
        pd.DataFrame([correction]).to_csv(correction_path, index=False)
    write_combined_report(combined, report_path, quality_summary, correction)
    outputs = {"flags": flags_path, "report": report_path, "sensor_quality": quality_path}
    if correction:
        outputs["temp_correction"] = correction_path
    return outputs


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
