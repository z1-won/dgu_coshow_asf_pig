"""Analyze ASF Dryad challenge data against project disease rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


DATASET_DOI = "10.5061/dryad.cnp5hqcm5"
DEFAULT_DATA_DIR = "data/raw/asf_dryad"
DEFAULT_OUTPUT_DIR = "artifacts/asf_dryad_validation"
RULES_PATH = "config/domain_rules.json"


def load_wide_csv(path: str | Path, value_name: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(col).strip() for col in df.columns]
    day_col = df.columns[0]
    out = df.melt(id_vars=[day_col], var_name="pig_id", value_name=value_name).dropna(subset=[value_name])
    out = out.rename(columns={day_col: "day_post_challenge"})
    out["day_post_challenge"] = pd.to_numeric(out["day_post_challenge"], errors="coerce")
    out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
    out = out.dropna(subset=["day_post_challenge", value_name]).copy()
    out["day_post_challenge"] = out["day_post_challenge"].astype(int)
    return out.reset_index(drop=True)


def current_rectal_threshold(path: str | Path = RULES_PATH) -> float:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    for rule in config["rules"]:
        if rule["id"] == "rectal_temp_high":
            return float(rule["threshold"])
    raise KeyError("rectal_temp_high rule not found")


def load_challenge_data(data_dir: str | Path) -> pd.DataFrame:
    base = Path(data_dir)
    temp = load_wide_csv(base / "Fig._1F_-_Temperature.csv", "rectal_temp")
    score = load_wide_csv(base / "Fig._1F_-_Clinical_scores.csv", "clinical_score")
    viral = load_wide_csv(base / "Fig._1H_-_Viral_loads_(blood).csv", "viral_load_blood")
    leukocytes = load_wide_csv(base / "Sup._Fig._3_-_Leukocytes.csv", "leukocytes")

    merged = temp.merge(score, on=["day_post_challenge", "pig_id"], how="outer")
    merged = merged.merge(viral, on=["day_post_challenge", "pig_id"], how="left")
    merged = merged.merge(leukocytes, on=["day_post_challenge", "pig_id"], how="left")
    merged["symptomatic"] = merged["clinical_score"].fillna(0) > 0
    merged["viral_detected"] = merged["viral_load_blood"].fillna(10) > 10
    merged["cohort"] = np.where(merged["pig_id"].str.startswith("Farm"), "Farm", "SPF")
    return merged.sort_values(["pig_id", "day_post_challenge"]).reset_index(drop=True)


def confusion_for_threshold(df: pd.DataFrame, threshold: float) -> dict[str, float]:
    scored = df.dropna(subset=["rectal_temp", "clinical_score"]).copy()
    rule = scored["rectal_temp"] >= threshold
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
        group = group.sort_values("day_post_challenge")
        symptomatic = group[group["clinical_score"].fillna(0) > 0]
        rule_hit = group[group["rectal_temp"].fillna(-np.inf) >= threshold]
        viral_hit = group[group["viral_load_blood"].fillna(10) > 10]
        max_score = group["clinical_score"].max()
        rows.append(
            {
                "pig_id": pig_id,
                "cohort": group["cohort"].iloc[0],
                "first_symptom_day": symptomatic["day_post_challenge"].min() if len(symptomatic) else np.nan,
                "first_temp_rule_day": rule_hit["day_post_challenge"].min() if len(rule_hit) else np.nan,
                "first_viral_detected_day": viral_hit["day_post_challenge"].min() if len(viral_hit) else np.nan,
                "max_clinical_score": float(max_score) if pd.notna(max_score) else np.nan,
                "max_rectal_temp": float(group["rectal_temp"].max()),
                "max_viral_load_blood": float(group["viral_load_blood"].max())
                if group["viral_load_blood"].notna().any()
                else np.nan,
                "min_leukocytes": float(group["leukocytes"].min()) if group["leukocytes"].notna().any() else np.nan,
            }
        )
    timeline = pd.DataFrame(rows)
    timeline["temp_lag_vs_symptom_day"] = timeline["first_temp_rule_day"] - timeline["first_symptom_day"]
    timeline["viral_lag_vs_symptom_day"] = timeline["first_viral_detected_day"] - timeline["first_symptom_day"]
    return timeline.sort_values(["max_clinical_score", "pig_id"], ascending=[False, True]).reset_index(drop=True)


def daily_summary(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    scored = df.copy()
    scored["temp_rule_fires"] = scored["rectal_temp"].fillna(-np.inf) >= threshold
    return (
        scored.groupby("day_post_challenge")
        .agg(
            observed_pigs=("pig_id", "nunique"),
            symptomatic_pigs=("symptomatic", "sum"),
            temp_rule_pigs=("temp_rule_fires", "sum"),
            viral_detected_pigs=("viral_detected", "sum"),
            mean_clinical_score=("clinical_score", "mean"),
            mean_rectal_temp=("rectal_temp", "mean"),
            max_rectal_temp=("rectal_temp", "max"),
        )
        .reset_index()
    )


def write_report(
    output_dir: Path,
    challenge: pd.DataFrame,
    sweep: pd.DataFrame,
    timeline: pd.DataFrame,
    daily: pd.DataFrame,
    threshold: float,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    challenge.to_csv(output_dir / "asf_challenge_daily_long.csv", index=False)
    sweep.to_csv(output_dir / "asf_rectal_temp_threshold_sweep.csv", index=False)
    timeline.to_csv(output_dir / "asf_per_pig_timeline.csv", index=False)
    daily.to_csv(output_dir / "asf_daily_summary.csv", index=False)

    chosen = sweep.loc[np.isclose(sweep["threshold"], threshold)].iloc[0]
    symptomatic_days = int(chosen["tp"] + chosen["fn"])
    rows = [
        "# ASF Dryad 실제 챌린지 검증",
        "",
        f"- 데이터 출처: Dryad `{DATASET_DOI}`",
        f"- challenge pig-days: `{int(chosen['n_pig_days'])}`",
        f"- pigs: `{challenge['pig_id'].nunique()}`",
        f"- symptomatic pig-days with temperature: `{symptomatic_days}`",
        f"- 현재 rectal_temp_high threshold: `{threshold}`",
        "",
        "## Threshold Sweep",
        "",
        dataframe_to_markdown(sweep),
        "",
        "## 개체별 발병/규칙/바이러스 검출 시점",
        "",
        dataframe_to_markdown(timeline),
        "",
        "## Challenge Day별 요약",
        "",
        dataframe_to_markdown(daily),
        "",
        "## 판단",
        "",
        "- `rectal_temp_high`는 정밀도 높은 규칙이지만, 온도 단독으로는 증상일 전체를 충분히 회수하지 못합니다.",
        "- viral load와 leukocyte 계열 지표는 ASF 특이성이 높지만, 현재 돈방 IoT 입력에는 없으므로 확진/수의검사 단계 보조 지표로 분리해야 합니다.",
        "- 따라서 프로젝트 흐름은 LSTM anomaly score + ASF 규칙 점수를 병렬로 계산하고, 단일 온도 규칙만으로 최종 판단하지 않는 방향이 맞습니다.",
    ]
    report = output_dir / "asf_dryad_validation_report.md"
    report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return report


def run_analysis(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    rules_path: str | Path = RULES_PATH,
) -> Path:
    threshold = current_rectal_threshold(rules_path)
    challenge = load_challenge_data(data_dir)
    sweep = threshold_sweep(challenge)
    timeline = per_pig_timeline(challenge, threshold)
    daily = daily_summary(challenge, threshold)
    return write_report(Path(output_dir), challenge, sweep, timeline, daily, threshold)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze ASF Dryad challenge data.")
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
