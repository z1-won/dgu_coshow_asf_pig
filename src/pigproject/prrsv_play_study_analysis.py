"""Analyze the PRRSV Play Study Dryad dataset against project disease rules.

The source workbooks stack two header rows for several sheets: row 0 is a
long descriptive name (what pandas reads as the column index) and row 1 is a
short variable code (e.g. "Final rectal temperature (Celsius)" over "temp").
`_promote_short_header` promotes that second row to the real column names.

`Clinical signs probability` also has ~210 extra rows with `dpi` values of
111/222/.../777 mixed in among the real -2..21 day range -- these are not
real days-post-infection (every other sheet in this workbook tops out at 21),
so they are filtered out rather than treated as real observations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


DEFAULT_DATA_DIR = "data/raw/external/prrsv_play_study"
DEFAULT_OUTPUT_DIR = "artifacts/prrsv_play_study_validation"
RULES_PATH = "config/domain_rules.json"
MAX_PLAUSIBLE_DPI = 30

CLINICAL_SIGN_COLUMNS = ["resp", "skincol", "cough", "rrate", "bc", "lam", "feces", "appet"]


def _promote_short_header(df: pd.DataFrame) -> pd.DataFrame:
    short_names = df.iloc[0].tolist()
    out = df.iloc[1:].copy()
    out.columns = short_names
    return out.reset_index(drop=True)


def _extract_leading_number(series: pd.Series) -> pd.Series:
    """Some clinical-sign cells mix a code with free text, e.g. '2(GREASY PIG)'."""
    extracted = series.astype(str).str.extract(r"(-?\d+\.?\d*)")[0]
    return pd.to_numeric(extracted, errors="coerce")


def load_rectal_temperature(data_dir: str | Path) -> pd.DataFrame:
    path = Path(data_dir) / "PRRSV_Play_study_Clinical_signs__rectal_temperature_and_medical_treatments.xlsx"
    df = _promote_short_header(pd.read_excel(path, sheet_name="Rectal temperature"))
    df = df.rename(columns={"pigid": "pig_id", "trt": "treatment", "temp": "rectal_temp_c"})
    df["pig_id"] = df["pig_id"].astype(str)
    df["dpi"] = pd.to_numeric(df["dpi"], errors="coerce")
    df["rectal_temp_c"] = pd.to_numeric(df["rectal_temp_c"], errors="coerce")
    return df.dropna(subset=["dpi", "rectal_temp_c"])[["pig_id", "treatment", "pen", "dpi", "rectal_temp_c"]]


def load_clinical_signs(data_dir: str | Path) -> pd.DataFrame:
    path = Path(data_dir) / "PRRSV_Play_study_Clinical_signs__rectal_temperature_and_medical_treatments.xlsx"
    df = _promote_short_header(pd.read_excel(path, sheet_name="Clinical signs probability"))
    df = df.rename(columns={"pigid": "pig_id", "trt": "treatment"})
    df["pig_id"] = df["pig_id"].astype(str)
    df["dpi"] = pd.to_numeric(df["dpi"], errors="coerce")
    df = df[df["dpi"].between(-MAX_PLAUSIBLE_DPI, MAX_PLAUSIBLE_DPI)]

    for col in CLINICAL_SIGN_COLUMNS:
        df[col] = _extract_leading_number(df[col])
    df["clinical_score"] = df[CLINICAL_SIGN_COLUMNS].sum(axis=1, min_count=1)
    return df.dropna(subset=["dpi"])[["pig_id", "treatment", "pen", "dpi", "clinical_score"]]


def load_activity_behavior(data_dir: str | Path) -> pd.DataFrame:
    path = Path(data_dir) / "PRRSV_Play_study_Play__exploratory__active__inactive__feeding_behaviours.xlsx"
    df = _promote_short_header(pd.read_excel(path, sheet_name="Active Inactive Feeding behav"))
    df = df.rename(columns={"pigid": "pig_id", "treatment": "treatment"})
    df["pig_id"] = df["pig_id"].astype(str)
    df["dpi"] = pd.to_numeric(df["dpi"], errors="coerce")
    for col in ["active_am", "active_pm", "inactive_am", "inactive_pm"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["active_count"] = df["active_am"] + df["active_pm"]
    df["inactive_count"] = df["inactive_am"] + df["inactive_pm"]
    return df.dropna(subset=["dpi"])[["pig_id", "treatment", "pen", "dpi", "active_count", "inactive_count"]]


def load_viral_load(data_dir: str | Path) -> pd.DataFrame:
    path = Path(data_dir) / "PRRSV_Play_study_Viral_load_RNA.xlsx"
    df = pd.read_excel(path, sheet_name="long stata final log10")
    df = df.rename(columns={"pigid": "pig_id", "log10rna/ml": "viral_load_log10"})
    df["pig_id"] = df["pig_id"].astype(str)
    df["dpi"] = pd.to_numeric(df["dpi"], errors="coerce")
    df["viral_load_log10"] = pd.to_numeric(df["viral_load_log10"], errors="coerce")
    return df.dropna(subset=["dpi"])[["pig_id", "treatment", "pen", "dpi", "viral_load_log10"]]


def load_medical_treatments(data_dir: str | Path) -> pd.DataFrame:
    path = Path(data_dir) / "PRRSV_Play_study_Clinical_signs__rectal_temperature_and_medical_treatments.xlsx"
    df = pd.read_excel(path, sheet_name="medical treatments - detailed")
    df = df.rename(columns={"pigid": "pig_id", "Medical treatment": "medical_treatment"})
    df["pig_id"] = df["pig_id"].astype(str)
    df["dpi"] = pd.to_numeric(df["dpi"], errors="coerce")
    return df.dropna(subset=["dpi"])[["pig_id", "treatment", "pen", "dpi", "medical_treatment"]]


def current_rectal_threshold(path: str | Path = RULES_PATH) -> float:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    for rule in config["rules"]:
        if rule["id"] == "rectal_temp_high":
            return float(rule["threshold"])
    raise KeyError("rectal_temp_high rule not found")


def build_daily_timeline(data_dir: str | Path) -> pd.DataFrame:
    temp = load_rectal_temperature(data_dir)
    clinical = load_clinical_signs(data_dir)
    activity = load_activity_behavior(data_dir)
    viral = load_viral_load(data_dir)
    treatments = load_medical_treatments(data_dir)

    merged = temp.merge(
        clinical[["pig_id", "dpi", "clinical_score"]], on=["pig_id", "dpi"], how="outer"
    )
    merged = merged.merge(
        activity[["pig_id", "dpi", "active_count", "inactive_count"]], on=["pig_id", "dpi"], how="outer"
    )
    merged = merged.merge(viral[["pig_id", "dpi", "viral_load_log10"]], on=["pig_id", "dpi"], how="outer")

    treated_days = treatments[["pig_id", "dpi"]].drop_duplicates()
    treated_days["treated"] = True
    merged = merged.merge(treated_days, on=["pig_id", "dpi"], how="left")
    merged["treated"] = merged["treated"].fillna(False)

    merged["symptomatic"] = merged["clinical_score"].fillna(0) > 0
    return merged.sort_values(["pig_id", "dpi"]).reset_index(drop=True)


def confusion_for_threshold(df: pd.DataFrame, threshold: float) -> dict[str, float]:
    scored = df.dropna(subset=["rectal_temp_c", "clinical_score"]).copy()
    rule = scored["rectal_temp_c"] >= threshold
    symptomatic = scored["clinical_score"] > 0
    tp = int((rule & symptomatic).sum())
    fn = int((~rule & symptomatic).sum())
    fp = int((rule & ~symptomatic).sum())
    tn = int((~rule & ~symptomatic).sum())
    sensitivity = tp / (tp + fn) if tp + fn else np.nan
    specificity = tn / (tn + fp) if tn + fp else np.nan
    precision = tp / (tp + fp) if tp + fp else np.nan
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision + sensitivity else np.nan
    return {
        "threshold": threshold,
        "n_pig_days": len(scored),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
    }


def threshold_sweep(df: pd.DataFrame, thresholds: list[float] | None = None) -> pd.DataFrame:
    thresholds = thresholds or [38.8, 39.0, 39.5, 39.8, 40.0, 40.5, 41.0]
    return pd.DataFrame([confusion_for_threshold(df, threshold) for threshold in thresholds])


def per_pig_timeline(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    for pig_id, group in df.groupby("pig_id"):
        group = group.sort_values("dpi")
        symptomatic = group[group["clinical_score"].fillna(0) > 0]
        rule_hit = group[group["rectal_temp_c"].fillna(-np.inf) >= threshold]
        treated = group[group["treated"]]
        max_score = group["clinical_score"].max()
        rows.append(
            {
                "pig_id": pig_id,
                "treatment": group["treatment"].dropna().iloc[0] if group["treatment"].notna().any() else np.nan,
                "first_symptom_dpi": symptomatic["dpi"].min() if len(symptomatic) else np.nan,
                "first_temp_rule_dpi": rule_hit["dpi"].min() if len(rule_hit) else np.nan,
                "first_treatment_dpi": treated["dpi"].min() if len(treated) else np.nan,
                "max_clinical_score": float(max_score) if pd.notna(max_score) else np.nan,
                "max_rectal_temp_c": float(group["rectal_temp_c"].max()) if group["rectal_temp_c"].notna().any() else np.nan,
                "max_viral_load_log10": float(group["viral_load_log10"].max())
                if group["viral_load_log10"].notna().any()
                else np.nan,
            }
        )
    timeline = pd.DataFrame(rows)
    timeline["temp_lag_vs_symptom_dpi"] = timeline["first_temp_rule_dpi"] - timeline["first_symptom_dpi"]
    timeline["treatment_lag_vs_symptom_dpi"] = timeline["first_treatment_dpi"] - timeline["first_symptom_dpi"]
    return timeline.sort_values(["max_clinical_score", "pig_id"], ascending=[False, True]).reset_index(drop=True)


def activity_shift_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in ["active_count", "inactive_count"]:
        healthy = df.loc[~df["symptomatic"], col].dropna()
        sick = df.loc[df["symptomatic"], col].dropna()
        rows.append(
            {
                "feature": col,
                "healthy_mean": float(healthy.mean()) if len(healthy) else np.nan,
                "symptomatic_mean": float(sick.mean()) if len(sick) else np.nan,
                "relative_change": float((sick.mean() - healthy.mean()) / healthy.mean())
                if len(healthy) and healthy.mean()
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def daily_summary(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    scored = df.copy()
    scored["temp_rule_fires"] = scored["rectal_temp_c"].fillna(-np.inf) >= threshold
    return (
        scored.groupby("dpi")
        .agg(
            observed_pigs=("pig_id", "nunique"),
            symptomatic_pigs=("symptomatic", "sum"),
            temp_rule_pigs=("temp_rule_fires", "sum"),
            mean_clinical_score=("clinical_score", "mean"),
            mean_rectal_temp_c=("rectal_temp_c", "mean"),
            mean_active_count=("active_count", "mean"),
        )
        .reset_index()
    )


def write_report(
    output_dir: Path,
    timeline_df: pd.DataFrame,
    sweep: pd.DataFrame,
    per_pig: pd.DataFrame,
    activity_shift: pd.DataFrame,
    daily: pd.DataFrame,
    threshold: float,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timeline_df.to_csv(output_dir / "prrsv_daily_timeline.csv", index=False)
    sweep.to_csv(output_dir / "prrsv_temperature_threshold_sweep.csv", index=False)
    per_pig.to_csv(output_dir / "prrsv_per_pig_timeline.csv", index=False)
    activity_shift.to_csv(output_dir / "prrsv_activity_shift_summary.csv", index=False)
    daily.to_csv(output_dir / "prrsv_daily_summary.csv", index=False)

    chosen = sweep.loc[np.isclose(sweep["threshold"], threshold)].iloc[0]
    symptomatic_days = int(chosen["tp"] + chosen["fn"])
    rows = [
        "# PRRSV Play Study 실제 challenge 검증",
        "",
        "데이터 출처: Dryad `10.5061/dryad.76hdr7t55` -- 이유자돈 30마리, PRRSV 감염 challenge, "
        "DPI(감염 후 경과일) 기준 체온/임상증상/행동/viral load 기록",
        "",
        f"- pig-days (체온+임상증상 모두 있는 행): `{int(chosen['n_pig_days'])}`",
        f"- pigs: `{timeline_df['pig_id'].nunique()}`",
        f"- symptomatic pig-days: `{symptomatic_days}`",
        f"- 현재 rectal_temp_high threshold: `{threshold}`",
        "",
        "## Threshold Sweep (rectal_temp_c >= threshold vs clinical_score > 0)",
        "",
        dataframe_to_markdown(sweep),
        "",
        "## 개체별 발병/규칙/치료 시점",
        "",
        dataframe_to_markdown(per_pig),
        "",
        "## 활동량 변화 (증상 유무 기준)",
        "",
        dataframe_to_markdown(activity_shift),
        "",
        "## DPI별 요약",
        "",
        dataframe_to_markdown(daily),
        "",
        "## 판단",
        "",
        "- `rectal_temp_high`는 ASF Dryad와 마찬가지로 PRRSV challenge에서도 정밀도는 있지만 "
        "체온 단독으로는 증상일 전체를 회수하지 못합니다 -- 서로 다른 두 질병에서 같은 결론이 나온다는 점이 "
        "체온 단독 판정을 지양하는 근거를 보강합니다.",
        "- 증상이 있는 날은 활동량(active_count)이 낮아지는 방향이 확인되면 `activity_drop` rule의 "
        "타 질병 일반화 가능성 근거로 쓸 수 있습니다.",
        "- 이 데이터는 ASF가 아니라 PRRSV(호흡기 질병) challenge입니다. 따라서 결론은 "
        "'ASF 탐지 증명'이 아니라 '체온/활동량 규칙이 실제 질병 challenge 전반에서 비슷하게 작동하는지'에 대한 "
        "두 번째 실제 질병 외부 검증입니다.",
    ]
    report = output_dir / "prrsv_play_study_validation_report.md"
    report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return report


def run_analysis(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    rules_path: str | Path = RULES_PATH,
) -> Path:
    threshold = current_rectal_threshold(rules_path)
    timeline_df = build_daily_timeline(data_dir)
    sweep = threshold_sweep(timeline_df)
    per_pig = per_pig_timeline(timeline_df, threshold)
    activity_shift = activity_shift_summary(timeline_df)
    daily = daily_summary(timeline_df, threshold)
    return write_report(Path(output_dir), timeline_df, sweep, per_pig, activity_shift, daily, threshold)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze PRRSV Play Study challenge data.")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rules-path", default=RULES_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_analysis(args.data_dir, args.output_dir, args.rules_path)
    print(f"Wrote {report}")


if __name__ == "__main__":
    main()
