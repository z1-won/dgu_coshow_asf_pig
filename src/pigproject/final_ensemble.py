"""Final chamber-level ensemble: union the per-track anomaly signals into one alert table.

This is NEXT_STEPS.md Step 9. The design there assumes both tracks cover the
same physical chamber and combines them as
``final_score = 0.65 * bioenergy_score + 0.35 * activity_score``. In practice
the two AI Hub tracks come from different farms and non-overlapping date
ranges (71408/71763: 2022-11 ~ 2023-09; 622: 2021), so no chamber currently
has both signals -- see docs/CHAMBER_TIMESERIES_LIMITATION.md for the related
per-pig density limitation uncovered on the bioenergy track. Rather than fake
a join that never fires, this module puts each track's own windows into one
common schema (same score scale, same tier cutoffs) and aggregates to a
chamber-level summary, so the 0.65/0.35 weighted formula only needs to be
switched on later, when a farm wires both sensor types to the same chamber.

AI Hub 71471 is intentionally excluded from this final table. Its pig
keypoint labels are useful as an auxiliary behavior-track validation source,
but its ESTRUS labels are separated by channel and the dataset has no ASF,
temperature, or environmental sensor labels. Keeping it out of the production
ensemble avoids treating a reproductive-behavior dataset as disease evidence.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown
from pigproject.domain_rules import MODEL_COMPONENT_CAP, MODEL_COMPONENT_WEIGHT, disease_tier_for

BIOENERGY_TRACK = "bioenergy"
ACTIVITY_TRACK = "activity_622"
CROSS_TRACK_WEIGHTS: dict[str, float] = {BIOENERGY_TRACK: 0.65, ACTIVITY_TRACK: 0.35}


def load_bioenergy_track(artifact_dir: str | Path) -> pd.DataFrame:
    """Standardize bioenergy_rule_flags.csv (model + rule layer already combined)."""
    df = pd.read_csv(Path(artifact_dir) / "bioenergy_rule_flags.csv", low_memory=False)
    return pd.DataFrame(
        {
            "track": BIOENERGY_TRACK,
            "source_dataset": df["dataset_key"].astype(str),
            "chamber_id": "bioenergy:" + df["dataset_key"].astype(str) + ":" + df["chamber_number"].astype(str),
            "start_datetime": pd.to_datetime(df["start_datetime"], errors="coerce"),
            "end_datetime": pd.to_datetime(df["end_datetime"], errors="coerce"),
            "model_component": df["model_component"],
            "rule_component": df["rule_component"],
            "track_score": df["disease_score"],
            "management_score": df["management_score"] if "management_score" in df.columns else 0.0,
            "environment_score": df["environment_score"] if "environment_score" in df.columns else 0.0,
            "alert_category": df["alert_category"] if "alert_category" in df.columns else "disease",
            "model_anomaly": df["model_anomaly"].astype(bool),
            "rule_anomaly": df["rule_anomaly"].astype(bool),
            "tier": df["disease_tier"],
            "reason": df["primary_reason"],
            "low_confidence": False,
        }
    )


def load_activity_track(artifact_dir: str | Path) -> pd.DataFrame:
    """Standardize the activity LSTM detection results onto the same score scale.

    There is no rule layer for the 622 behavior features yet (only the
    bioenergy track has one -- see domain_rules.py), so rule_component is
    always 0 here and track_score is model-only. That caps this track below
    the "high" disease tier (which requires rule co-occurrence on top of the
    model signal), which is the intended, conservative behavior for a
    single-signal track rather than a bug.
    """
    artifacts = Path(artifact_dir)
    df = pd.read_csv(artifacts / "lstm_val_results.csv", low_memory=False)
    threshold = float(np.load(artifacts / "threshold.npy"))
    ratio = (df["reconstruction_error"] / threshold).clip(upper=MODEL_COMPONENT_CAP)
    model_component = MODEL_COMPONENT_WEIGHT * ratio
    confirmed = df["confirmed_anomaly"].astype(bool)

    # lstm_val_results.csv already carries low_confidence from
    # activity_split_summary.csv (activity_model_dataset.py) when the report
    # was built with pig-activity-report; fall back to False (old artifacts
    # / bioenergy-style callers without the column) rather than failing.
    low_confidence = df["low_confidence"].astype(bool) if "low_confidence" in df.columns else False

    return pd.DataFrame(
        {
            "track": ACTIVITY_TRACK,
            "source_dataset": "622",
            "chamber_id": (
                "activity622:facility" + df["facility_number"].astype(str) + ":pen" + df["pen_number"].astype(str)
            ),
            "start_datetime": pd.to_datetime(df["start_datetime"], errors="coerce"),
            "end_datetime": pd.to_datetime(df["end_datetime"], errors="coerce"),
            "model_component": model_component,
            "rule_component": 0.0,
            "track_score": model_component,
            "management_score": 0.0,
            "environment_score": 0.0,
            "alert_category": np.where(confirmed, "disease", ""),
            "model_anomaly": confirmed,
            "rule_anomaly": False,
            "tier": model_component.apply(disease_tier_for),
            "reason": np.where(confirmed, "model reconstruction error threshold 초과 (activity)", ""),
            "low_confidence": low_confidence,
        }
    )


def build_final_table(track_frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Union all tracks' standardized windows and derive final_alert = model OR rule."""
    combined = pd.concat(track_frames, ignore_index=True)
    combined["final_alert"] = combined["model_anomaly"].fillna(False) | combined["rule_anomaly"].fillna(False)
    combined["operational_alert"] = (
        combined["final_alert"].fillna(False)
        | (combined.get("management_score", 0) >= 0.6)
        | (combined.get("environment_score", 0) >= 0.8)
    )
    return combined.sort_values("track_score", ascending=False).reset_index(drop=True)


def summarize_by_chamber(combined: pd.DataFrame) -> pd.DataFrame:
    """Roll windows up to one row per (track, chamber) -- the actual 'final chamber score'.

    low_confidence is constant within a chamber (it comes from that chamber's
    own train-window count, not from any individual window), so "any" is
    just a convenient reduction, not really an aggregation choice.
    """
    summary = (
        combined.groupby(["track", "source_dataset", "chamber_id"], dropna=False)
        .agg(
            windows=("track_score", "size"),
            mean_score=("track_score", "mean"),
            max_score=("track_score", "max"),
            alert_windows=("final_alert", "sum"),
            operational_alert_windows=("operational_alert", "sum"),
            high_tier_windows=("tier", lambda s: int((s == "high").sum())),
            low_confidence=("low_confidence", "any"),
        )
        .reset_index()
    )
    summary["chamber_tier"] = summary["max_score"].apply(disease_tier_for)
    return summary.sort_values("max_score", ascending=False).reset_index(drop=True)


def write_report(combined: pd.DataFrame, chamber_summary: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    track_counts = combined["track"].value_counts()
    alerts = combined[combined["final_alert"]]
    normal_chambers = chamber_summary[~chamber_summary["low_confidence"]]
    low_confidence_chambers = chamber_summary[chamber_summary["low_confidence"]]
    top_chambers = normal_chambers.head(10)
    summary_cols = [
        "track",
        "source_dataset",
        "chamber_id",
        "windows",
        "mean_score",
        "max_score",
        "alert_windows",
        "operational_alert_windows",
        "high_tier_windows",
        "chamber_tier",
    ]

    lines = [
        "# 최종 돈방 단위 경보 리포트 (Track 통합)",
        "",
        "## 커버리지",
        "",
        f"- 전체 window: `{len(combined)}` (bioenergy: `{int(track_counts.get(BIOENERGY_TRACK, 0))}`, "
        f"activity_622: `{int(track_counts.get(ACTIVITY_TRACK, 0))}`)",
        f"- 전체 chamber(track별로 구분): `{combined['chamber_id'].nunique()}`",
        f"- 최종 경보(model OR rule) window: `{int(combined['final_alert'].sum())}`",
        f"- 운영 경보(disease/management/environment) window: `{int(combined['operational_alert'].sum())}`",
        "",
        "## 두 track을 아직 가중 평균으로 합치지 않는 이유",
        "",
        "`bioenergy`(71408/71763)와 `activity_622`(622)는 서로 다른 농장/기간에서 수집된 "
        "별도 AI Hub 데이터셋이라 같은 물리적 돈방을 가리키는 chamber_id가 하나도 겹치지 않습니다. "
        "그래서 지금은 각 track의 window를 같은 점수 척도(model_component + rule_component, "
        "0~1 model 성분 + rule 성분)로 표준화해 하나의 테이블/요약으로만 모았습니다. "
        f"두 track이 같은 돈방을 가리키는 실데이터가 들어오면 `final_score = "
        f"{CROSS_TRACK_WEIGHTS[BIOENERGY_TRACK]} * bioenergy_score + "
        f"{CROSS_TRACK_WEIGHTS[ACTIVITY_TRACK]} * activity_score`로 합치는 것이 다음 단계입니다.",
        "",
        "## 71471을 최종 ensemble에 넣지 않는 이유",
        "",
        "AI Hub 71471은 돼지 keypoints와 행동 라벨이 있어 행동량 보조 검증에는 쓸 수 있습니다. "
        "하지만 ASF 라벨, 체온, 환경센서가 없고 `ESTRUS=Y/N`이 channel별로 분리되어 있어 "
        "발정 효과와 카메라/channel 효과를 분리하기 어렵습니다. 71471 전용 행동 baseline에서도 "
        "발정 validation 구간이 정상 validation보다 강한 confirmed anomaly로 잡히지 않았으므로, "
        "현재 최종 돈방 경보 ensemble에는 포함하지 않습니다.",
        "",
        "## Chamber별 요약 (상위 10, max_score 기준, 참고용 chamber 제외)",
        "",
        dataframe_to_markdown(top_chambers[summary_cols]),
    ]
    if len(low_confidence_chambers):
        lines += [
            "",
            "## 참고용(데이터 부족) chamber -- 순위/경보에서 제외",
            "",
            "학습 시퀀스가 너무 적어(`activity_model_dataset.LOW_TRAIN_WINDOWS_THRESHOLD` 미만) "
            "reconstruction error가 그 pen의 실제 정상 기준을 반영한다고 보기 어려운 chamber입니다. "
            "window/점수는 아래에 그대로 남기되, 위 순위표에서는 제외했습니다.",
            "",
            dataframe_to_markdown(low_confidence_chambers[summary_cols]),
        ]
    lines += [
        "",
        "## 경보 window (model 또는 rule 기준 최종 경보)",
        "",
        dataframe_to_markdown(
            alerts[
                [
                    "track",
                    "chamber_id",
                    "start_datetime",
                    "end_datetime",
                    "alert_category",
                    "track_score",
                    "management_score",
                    "environment_score",
                    "tier",
                    "reason",
                ]
            ]
        )
        if len(alerts)
        else "경보 없음.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Union bioenergy + activity anomaly tracks into one final chamber-level alert table."
    )
    parser.add_argument("--bioenergy-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--activity-dir", default="artifacts/activity_model_10min")
    parser.add_argument("--output-csv", default="data/processed/final_chamber_anomaly_scores.csv")
    parser.add_argument("--chamber-summary-csv", default="artifacts/final_chamber_summary.csv")
    parser.add_argument("--report", default="artifacts/final_chamber_alert_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    track_frames = [load_bioenergy_track(args.bioenergy_dir), load_activity_track(args.activity_dir)]
    combined = build_final_table(track_frames)
    chamber_summary = summarize_by_chamber(combined)

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_csv, index=False)

    chamber_summary_csv = Path(args.chamber_summary_csv)
    chamber_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    chamber_summary.to_csv(chamber_summary_csv, index=False)

    report_path = write_report(combined, chamber_summary, args.report)

    print(f"windows: {output_csv}")
    print(f"chamber summary: {chamber_summary_csv}")
    print(f"report: {report_path}")
    print(f"final alert windows: {int(combined['final_alert'].sum())} / {len(combined)}")


if __name__ == "__main__":
    main()
