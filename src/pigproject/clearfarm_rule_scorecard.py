"""Score ClearFarm rule hits and evaluate score thresholds.

This module sits one step above ``clearfarm_rule_validation``. That module
checks individual thresholds; this one asks the operational question: if rule
hits become weighted scores, which alert cutoff gives a usable recall/precision
tradeoff against ClearFarm health observations?
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.clearfarm_processing import DEFAULT_INPUT_DIR as DEFAULT_CLEARFARM_RAW_DIR
from pigproject.clearfarm_rule_validation import (
    DEFAULT_PEN_DAY_PATH,
    RuleThresholds,
    confusion_for_threshold,
    load_rule_thresholds,
    prepare_subdaily_validation_frame,
)
from pigproject.domain_rules import CO_OCCURRENCE_BONUS_PER_EXTRA_RULE, SEVERITY_WEIGHTS


DEFAULT_ARTIFACT_DIR = "artifacts/clearfarm_rule_scorecard"
DEFAULT_RULES_CONFIG = "config/domain_rules_clearfarm.json"

SCORE_THRESHOLDS = [0.3, 0.6, 0.8, 0.9, 1.0, 1.2, 1.5]


def add_rule_scores(df: pd.DataFrame, thresholds: RuleThresholds) -> pd.DataFrame:
    scored = df.copy()
    scored["rule_feed_drop"] = scored["feed_intake_daily_min_zscore_3d"] <= thresholds.feed_drop
    scored["rule_co2_high"] = scored["co2_max"] >= thresholds.co2_high
    scored["rule_nh3_high"] = scored["ammonia_max"] >= thresholds.nh3_high
    scored["rule_barn_temp_high"] = scored["temperature_max"] >= thresholds.barn_temp_high
    if thresholds.humidity_high is not None and "humidity_max" in scored.columns:
        scored["rule_humidity_high"] = scored["humidity_max"] >= thresholds.humidity_high
    else:
        scored["rule_humidity_high"] = False

    scored["management_score"] = np.where(scored["rule_feed_drop"], SEVERITY_WEIGHTS["medium"], 0.0)

    environment_rule_cols = ["rule_co2_high", "rule_nh3_high", "rule_barn_temp_high", "rule_humidity_high"]
    environment_hits = scored[environment_rule_cols].sum(axis=1)
    environment_severity = (
        np.where(scored["rule_co2_high"], SEVERITY_WEIGHTS["low"], 0.0)
        + np.where(scored["rule_nh3_high"], SEVERITY_WEIGHTS["low"], 0.0)
        + np.where(scored["rule_barn_temp_high"], SEVERITY_WEIGHTS["medium"], 0.0)
        + np.where(scored["rule_humidity_high"], SEVERITY_WEIGHTS["low"], 0.0)
    )
    environment_bonus = CO_OCCURRENCE_BONUS_PER_EXTRA_RULE * np.maximum(0, environment_hits - 1)
    scored["environment_score"] = environment_severity + environment_bonus

    all_rule_cols = ["rule_feed_drop", *environment_rule_cols]
    all_hits = scored[all_rule_cols].sum(axis=1)
    all_severity = scored["management_score"] + environment_severity
    all_bonus = CO_OCCURRENCE_BONUS_PER_EXTRA_RULE * np.maximum(0, all_hits - 1)
    scored["rule_triggered_count"] = all_hits.astype(int)
    scored["rule_score"] = all_severity + all_bonus
    scored["feed_env_score"] = scored["management_score"] + scored["environment_score"]

    reason_cols = all_rule_cols
    scored["rule_reasons"] = [
        ",".join(col.removeprefix("rule_") for col in reason_cols if bool(row[col]))
        for _, row in scored.iterrows()
    ]
    return scored


def score_sweep(scored: pd.DataFrame, score_col: str, sign_col: str, thresholds: list[float]) -> pd.DataFrame:
    rows = []
    for threshold in thresholds:
        result = confusion_for_threshold(scored, score_col, threshold, sign_col, direction="above")
        result["score_col"] = score_col
        result["sign_col"] = sign_col
        result["n_alerts"] = result["tp"] + result["fp"]
        rows.append(result)
    return pd.DataFrame(rows)[
        [
            "score_col",
            "sign_col",
            "threshold",
            "n",
            "n_alerts",
            "tp",
            "fn",
            "fp",
            "tn",
            "sensitivity",
            "specificity",
            "precision",
            "f1",
        ]
    ]


def build_scorecard(
    pen_day_path: str | Path = DEFAULT_PEN_DAY_PATH,
    raw_dir: str | Path = DEFAULT_CLEARFARM_RAW_DIR,
    rules_config: str | Path = DEFAULT_RULES_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame, RuleThresholds]:
    thresholds = load_rule_thresholds(rules_config)
    frame = prepare_subdaily_validation_frame(pen_day_path, raw_dir)
    scored = add_rule_scores(frame, thresholds)
    sweeps = pd.concat(
        [
            score_sweep(scored, "rule_score", "any_signs", SCORE_THRESHOLDS),
            score_sweep(scored, "feed_env_score", "any_signs", SCORE_THRESHOLDS),
            score_sweep(scored, "management_score", "gut_signs", [0.6]),
            score_sweep(scored, "environment_score", "respiratory_signs", SCORE_THRESHOLDS),
            score_sweep(scored, "environment_score", "heat_signs", SCORE_THRESHOLDS),
        ],
        ignore_index=True,
    )
    return scored, sweeps, thresholds


def best_rows(sweeps: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (score_col, sign_col), group in sweeps.groupby(["score_col", "sign_col"]):
        valid = group.dropna(subset=["f1"])
        if len(valid) == 0:
            continue
        rows.append(valid.sort_values(["f1", "precision", "sensitivity"], ascending=False).iloc[0])
    return pd.DataFrame(rows).reset_index(drop=True)


def format_scorecard_table(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in ["sensitivity", "specificity", "precision", "f1"]:
        if col in formatted.columns:
            formatted[col] = formatted[col].map(lambda value: "" if pd.isna(value) else f"{value:.1%}")
    for col in ["rule_score", "feed_env_score", "management_score", "environment_score"]:
        if col in formatted.columns:
            formatted[col] = formatted[col].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    return formatted


def write_scorecard_outputs(
    scored: pd.DataFrame,
    sweeps: pd.DataFrame,
    thresholds: RuleThresholds,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> tuple[Path, Path, Path]:
    output = Path(artifact_dir)
    output.mkdir(parents=True, exist_ok=True)
    scored_path = output / "clearfarm_rule_scored_pen_days.csv"
    sweep_path = output / "clearfarm_rule_score_threshold_sweep.csv"
    report_path = output / "clearfarm_rule_scorecard_report.md"
    scored.to_csv(scored_path, index=False)
    sweeps.to_csv(sweep_path, index=False)

    best = best_rows(sweeps)
    top_alerts = scored.sort_values(["rule_score", "feed_env_score"], ascending=False).head(20)
    show_alerts = top_alerts[
        [
            "experiment",
            "pen_id",
            "date",
            "rule_score",
            "feed_env_score",
            "management_score",
            "environment_score",
            "rule_triggered_count",
            "rule_reasons",
            "any_signs",
            "respiratory_signs",
            "gut_signs",
            "heat_signs",
        ]
    ]

    lines = [
        "# ClearFarm Rule Scorecard",
        "",
        f"적용 config: `{thresholds.source}`",
        "",
        "## 적용 threshold",
        "",
        f"- feed_drop: `{thresholds.feed_drop:g}`",
        f"- co2_high: `{thresholds.co2_high:g}`",
        f"- nh3_high: `{thresholds.nh3_high:g}`",
        f"- barn_temp_high: `{thresholds.barn_temp_high:g}`",
        f"- humidity_high: `{thresholds.humidity_high:g}`" if thresholds.humidity_high is not None else "- humidity_high: 비활성",
        "",
        "## Best F1 Rows",
        "",
        dataframe_to_markdown(format_scorecard_table(best)),
        "",
        "## Threshold Sweep",
        "",
        dataframe_to_markdown(format_scorecard_table(sweeps)),
        "",
        "## Top 20 Scored Pen-Days",
        "",
        dataframe_to_markdown(format_scorecard_table(show_alerts)),
        "",
        "## 판단",
        "",
        "- 단일 hit/미hit보다 score threshold sweep이 의사결정에 더 적합하다.",
        "- `rule_score`는 management와 environment의 동시발생을 보상하므로, 조기 선별용 후보 점수로 우선 볼 만하다.",
        "- 다만 ClearFarm 라벨은 관찰일에만 존재하므로, 이 결과는 운영 배포 성능이 아니라 외부 라벨 기반 sanity check로 해석해야 한다.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return scored_path, sweep_path, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ClearFarm rule scorecard from calibrated thresholds.")
    parser.add_argument("--pen-day-path", default=DEFAULT_PEN_DAY_PATH)
    parser.add_argument("--raw-dir", default=DEFAULT_CLEARFARM_RAW_DIR)
    parser.add_argument("--rules-config", default=DEFAULT_RULES_CONFIG)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scored, sweeps, thresholds = build_scorecard(args.pen_day_path, args.raw_dir, args.rules_config)
    scored_path, sweep_path, report_path = write_scorecard_outputs(scored, sweeps, thresholds, args.artifact_dir)
    print(f"scored: {scored_path}")
    print(f"sweep: {sweep_path}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
