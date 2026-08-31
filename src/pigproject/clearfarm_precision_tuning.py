"""Tune precision filters for ClearFarm recall-candidate alerts.

The recall candidate intentionally widens the alert net. This module tests
whether the newly added alerts can be filtered with simple operational guards
while keeping most of the recall gain.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.clearfarm_rule_validation import confusion_for_threshold


DEFAULT_BASELINE_SCORED = "artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_scored_pen_days.csv"
DEFAULT_CANDIDATE_SCORED = (
    "artifacts/clearfarm_rule_scorecard/recall_candidate_config/clearfarm_rule_scored_pen_days.csv"
)
DEFAULT_OUTPUT_DIR = "artifacts/clearfarm_precision_tuning/full_recall_candidate"
ALERT_THRESHOLD = 0.3

KEY_COLUMNS = ["experiment", "pen_id", "date"]
SIGN_COLUMNS = ["any_signs", "respiratory_signs", "gut_signs", "heat_signs"]
RULE_COLUMNS = [
    "rule_feed_drop",
    "rule_co2_high",
    "rule_nh3_high",
    "rule_barn_temp_high",
    "rule_humidity_high",
]


def _read_scored(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False, parse_dates=["date"])
    df["experiment"] = df["experiment"].astype(str)
    df["pen_id"] = df["pen_id"].astype(str)
    missing_rule_cols = [col for col in RULE_COLUMNS if col not in df.columns]
    if missing_rule_cols:
        df = pd.concat([df, pd.DataFrame(False, index=df.index, columns=missing_rule_cols)], axis=1)
    for col in RULE_COLUMNS:
        df[col] = df[col].fillna(False).astype(bool)
    for col in SIGN_COLUMNS:
        df[col] = df[col].fillna(False).astype(bool)
    df["rule_reasons"] = df.get("rule_reasons", "").fillna("").astype(str)
    return df.sort_values(KEY_COLUMNS).reset_index(drop=True)


def _reason_count(reasons: pd.Series) -> pd.Series:
    return reasons.fillna("").map(lambda value: 0 if not value else len([part for part in value.split(",") if part]))


def build_precision_frame(
    baseline_scored_path: str | Path = DEFAULT_BASELINE_SCORED,
    candidate_scored_path: str | Path = DEFAULT_CANDIDATE_SCORED,
    alert_threshold: float = ALERT_THRESHOLD,
) -> pd.DataFrame:
    baseline = _read_scored(baseline_scored_path)
    candidate = _read_scored(candidate_scored_path)

    keep_cols = KEY_COLUMNS + [
        "rule_score",
        "feed_env_score",
        "management_score",
        "environment_score",
        "rule_triggered_count",
        "rule_reasons",
        *RULE_COLUMNS,
        *SIGN_COLUMNS,
        "month",
        "is_jan_to_may",
    ]
    frame = baseline[keep_cols].merge(
        candidate[keep_cols],
        on=KEY_COLUMNS,
        how="inner",
        suffixes=("_baseline", "_candidate"),
    )
    frame["baseline_alert"] = frame["rule_score_baseline"] >= alert_threshold
    frame["candidate_alert"] = frame["rule_score_candidate"] >= alert_threshold
    frame["added_alert"] = frame["candidate_alert"] & ~frame["baseline_alert"]
    frame["candidate_reason_count"] = _reason_count(frame["rule_reasons_candidate"])
    frame["month"] = frame["month_candidate"]
    frame["is_jan_to_may"] = frame["is_jan_to_may_candidate"].astype(bool)

    frame = add_recent_alert_context(frame)
    return frame


def add_recent_alert_context(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(KEY_COLUMNS).copy()
    out["candidate_alert_in_previous_observed_14d"] = False
    out["same_reason_alert_in_previous_observed_14d"] = False
    for _, idx in out.groupby(["experiment", "pen_id"], sort=False).groups.items():
        group = out.loc[idx].sort_values("date")
        prev_alert_dates: list[pd.Timestamp] = []
        prev_reason_dates: dict[str, list[pd.Timestamp]] = {}
        for row_idx, row in group.iterrows():
            current_date = pd.Timestamp(row["date"])
            recent_any = any((current_date - prior).days <= 14 for prior in prev_alert_dates)
            reasons = str(row["rule_reasons_candidate"] or "")
            reason_parts = [part for part in reasons.split(",") if part]
            recent_same_reason = any(
                any((current_date - prior).days <= 14 for prior in prev_reason_dates.get(part, []))
                for part in reason_parts
            )
            out.at[row_idx, "candidate_alert_in_previous_observed_14d"] = bool(recent_any)
            out.at[row_idx, "same_reason_alert_in_previous_observed_14d"] = bool(recent_same_reason)
            if bool(row["candidate_alert"]):
                prev_alert_dates.append(current_date)
                for part in reason_parts:
                    prev_reason_dates.setdefault(part, []).append(current_date)
    return out


def _has_reason(frame: pd.DataFrame, reason: str) -> pd.Series:
    return frame["rule_reasons_candidate"].str.split(",").map(lambda parts: reason in parts)


def build_policy_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    added = frame["added_alert"]
    cooccurrence = frame["candidate_reason_count"] >= 2
    triple_env = frame["rule_reasons_candidate"] == "co2_high,nh3_high,humidity_high"
    nh3_with_humidity = frame["rule_reasons_candidate"] == "nh3_high,humidity_high"
    single_nh3 = frame["rule_reasons_candidate"] == "nh3_high"
    single_co2 = frame["rule_reasons_candidate"] == "co2_high"
    recent_same_reason = frame["same_reason_alert_in_previous_observed_14d"]
    recent_any = frame["candidate_alert_in_previous_observed_14d"]

    masks = {
        "baseline_only": frame["baseline_alert"],
        "recall_candidate_all": frame["candidate_alert"],
        "added_score_0_6": frame["baseline_alert"] | (added & (frame["rule_score_candidate"] >= 0.6)),
        "added_env_cooccurrence": frame["baseline_alert"] | (added & cooccurrence),
        "added_high_match_reasons": frame["baseline_alert"] | (added & (triple_env | single_nh3 | single_co2)),
        "added_nh3_or_triple_env": frame["baseline_alert"] | (added & (triple_env | nh3_with_humidity | single_nh3)),
        "added_recent_any_14d": frame["baseline_alert"] | (added & recent_any),
        "added_recent_same_reason_14d": frame["baseline_alert"] | (added & recent_same_reason),
        "added_cooccurrence_or_recent_same_reason": frame["baseline_alert"]
        | (added & (cooccurrence | recent_same_reason)),
    }
    return masks


def _metrics_for_mask(df: pd.DataFrame, alert: pd.Series, policy_name: str, scope: str) -> dict[str, float | int | str]:
    work = df.copy()
    work["policy_alert"] = alert.astype(float)
    result = confusion_for_threshold(work, "policy_alert", 0.5, "any_signs_candidate", direction="above")
    added = work["added_alert"]
    added_kept = added & alert
    added_dropped = added & ~alert
    result.update(
        {
            "policy": policy_name,
            "scope": scope,
            "n_alerts": result["tp"] + result["fp"],
            "added_kept": int(added_kept.sum()),
            "added_dropped": int(added_dropped.sum()),
            "added_kept_match_rate": float(work.loc[added_kept, "any_signs_candidate"].mean())
            if int(added_kept.sum())
            else np.nan,
            "added_dropped_match_rate": float(work.loc[added_dropped, "any_signs_candidate"].mean())
            if int(added_dropped.sum())
            else np.nan,
        }
    )
    return result


def evaluate_precision_policies(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    masks = build_policy_masks(frame)
    rows = []
    for scope, scoped in [("all", frame), ("jan_may", frame[frame["is_jan_to_may"]])]:
        scoped_masks = build_policy_masks(scoped)
        for name, mask in scoped_masks.items():
            rows.append(_metrics_for_mask(scoped, mask, name, scope))
    metrics = pd.DataFrame(rows)[
        [
            "policy",
            "scope",
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
            "added_kept",
            "added_dropped",
            "added_kept_match_rate",
            "added_dropped_match_rate",
        ]
    ]

    reason_summary = (
        frame[frame["added_alert"]]
        .groupby("rule_reasons_candidate", dropna=False)
        .agg(
            added_alerts=("added_alert", "size"),
            matched_any_signs=("any_signs_candidate", "sum"),
            recent_any_14d=("candidate_alert_in_previous_observed_14d", "sum"),
            recent_same_reason_14d=("same_reason_alert_in_previous_observed_14d", "sum"),
        )
        .reset_index(names="rule_reasons")
    )
    reason_summary["match_rate"] = reason_summary["matched_any_signs"] / reason_summary["added_alerts"]
    reason_summary["recent_same_reason_rate"] = (
        reason_summary["recent_same_reason_14d"] / reason_summary["added_alerts"]
    )
    reason_summary = reason_summary.sort_values(["match_rate", "added_alerts"], ascending=[False, False])
    return metrics, reason_summary


def choose_recommended_policy(metrics: pd.DataFrame) -> pd.Series:
    full = metrics[metrics["scope"] == "all"].copy()
    baseline = full[full["policy"] == "baseline_only"].iloc[0]
    candidates = full[~full["policy"].isin(["baseline_only", "recall_candidate_all"])].copy()
    candidates = candidates[candidates["sensitivity"] >= baseline["sensitivity"]]
    if len(candidates) == 0:
        return full[full["policy"] == "baseline_only"].iloc[0]
    candidates["precision_gain"] = candidates["precision"] - baseline["precision"]
    candidates["recall_gain"] = candidates["sensitivity"] - baseline["sensitivity"]
    candidates["alert_delta"] = candidates["n_alerts"] - baseline["n_alerts"]
    return candidates.sort_values(
        ["f1", "precision_gain", "recall_gain", "alert_delta"],
        ascending=[False, False, False, True],
    ).iloc[0]


def _format_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in [
        "sensitivity",
        "specificity",
        "precision",
        "f1",
        "added_kept_match_rate",
        "added_dropped_match_rate",
        "match_rate",
        "recent_same_reason_rate",
    ]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: "" if pd.isna(value) else f"{value:.1%}")
    return out


def write_precision_outputs(
    frame: pd.DataFrame,
    metrics: pd.DataFrame,
    reason_summary: pd.DataFrame,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path, Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame_path = output / "clearfarm_precision_tuning_frame.csv"
    metrics_path = output / "clearfarm_precision_policy_metrics.csv"
    reason_path = output / "clearfarm_precision_added_reason_summary.csv"
    report_path = output / "clearfarm_precision_tuning_report.md"

    frame.to_csv(frame_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    reason_summary.to_csv(reason_path, index=False)

    baseline = metrics[(metrics["scope"] == "all") & (metrics["policy"] == "baseline_only")].iloc[0]
    recall_all = metrics[(metrics["scope"] == "all") & (metrics["policy"] == "recall_candidate_all")].iloc[0]
    recommended = choose_recommended_policy(metrics)
    jan_may = metrics[metrics["scope"] == "jan_may"].copy()

    lines = [
        "# ClearFarm 전체 후보 정밀도 개선 실험",
        "",
        "## 실험 목적",
        "",
        "- recall 후보 config가 새로 추가한 알림을 모두 운영 알림으로 올리지 않고, 정밀도 필터를 붙였을 때의 성능을 본다.",
        "- 기존 baseline 알림은 유지하고, candidate가 새로 추가한 알림에만 필터를 적용했다.",
        "- 현재 평가는 ClearFarm 건강 관찰일 기준이다. 실제 lead-time은 농장 이벤트 로그가 쌓이면 별도 산출해야 한다.",
        "",
        "## 전체 기간 성능",
        "",
        dataframe_to_markdown(_format_table(metrics[metrics["scope"] == "all"])),
        "",
        "## 1~5월 성능",
        "",
        dataframe_to_markdown(_format_table(jan_may)),
        "",
        "## 추가 알림 원인별 품질",
        "",
        dataframe_to_markdown(_format_table(reason_summary)),
        "",
        "## 추천안",
        "",
        f"- 추천 policy: `{recommended['policy']}`",
        f"- baseline 대비 recall: `{baseline['sensitivity']:.1%}` -> `{recommended['sensitivity']:.1%}`",
        f"- baseline 대비 precision: `{baseline['precision']:.1%}` -> `{recommended['precision']:.1%}`",
        f"- baseline 대비 F1: `{baseline['f1']:.1%}` -> `{recommended['f1']:.1%}`",
        f"- 알림 수: `{int(baseline['n_alerts'])}` -> `{int(recommended['n_alerts'])}`",
        "",
        "## 해석",
        "",
        f"- recall 후보 전체 적용은 recall `{recall_all['sensitivity']:.1%}`까지 올리지만 알림 수가 "
        f"`{int(recall_all['n_alerts'])}`건으로 늘어난다.",
        "- 정밀도 개선의 핵심은 환경 단일 이상을 바로 확정 알림으로 올리지 않고, 다중 환경 신호나 최근 반복 신호일 때만 살리는 것이다.",
        "- 운영 UI에서는 이 결과를 `주의 후보`와 `확인 필요`로 분리해서 보여주는 것이 맞다.",
        "",
        "## 다음 행동",
        "",
        "- 추천 policy를 ClearFarm 3단계 알림 정책에 연결해 `observe`와 `cctv_focus` 사이의 중간 필터로 적용한다.",
        "- 이후 dashboard 성능 페이지에 baseline / recall candidate / precision-tuned candidate를 나란히 표시한다.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame_path, metrics_path, reason_path, report_path


def run_precision_tuning(
    baseline_scored_path: str | Path = DEFAULT_BASELINE_SCORED,
    candidate_scored_path: str | Path = DEFAULT_CANDIDATE_SCORED,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Path]:
    frame = build_precision_frame(baseline_scored_path, candidate_scored_path)
    metrics, reason_summary = evaluate_precision_policies(frame)
    _, _, _, report = write_precision_outputs(frame, metrics, reason_summary, output_dir)
    return frame, metrics, reason_summary, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune ClearFarm recall-candidate precision filters.")
    parser.add_argument("--baseline-scored", default=DEFAULT_BASELINE_SCORED)
    parser.add_argument("--candidate-scored", default=DEFAULT_CANDIDATE_SCORED)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, metrics, _, report = run_precision_tuning(args.baseline_scored, args.candidate_scored, args.output_dir)
    recommended = choose_recommended_policy(metrics)
    print(f"recommended_policy: {recommended['policy']}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
