"""Compare AI Hub 71471 behavior time series with the 622 activity track."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


FEATURE_MAPPING = {
    "annotation_count": "point_annotation_count",
    "visible_keypoints_sum": "total_keypoints",
    "center_movement_proxy": "center_movement",
    "center_movement_norm": "center_movement_norm",
    "mean_center_x": "mean_center_x",
    "mean_center_y": "mean_center_y",
    "mean_span_x": "mean_span_x",
    "mean_span_y": "mean_span_y",
    "max_span_x": "max_span_x",
    "max_span_y": "max_span_y",
    "active_behavior_ratio": "active_behavior_ratio",
    "rest_behavior_ratio": "rest_behavior_ratio",
    "lying_ratio": "lying_ratio",
    "eating_ratio": "eating_ratio",
    "standing_ratio": "standing_ratio",
    "sitting_ratio": "sitting_ratio",
    "frame_count": "frame_count",
}

LABEL_ONLY_71471 = ["estrus_ratio", "estrus_positive_count", "injected_ratio", "injected_count"]


def load_timeseries(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    return df.dropna(subset=["datetime"]).reset_index(drop=True)


def summarize_dataset(name: str, df: pd.DataFrame, group_cols: list[str]) -> dict[str, object]:
    summary: dict[str, object] = {
        "dataset": name,
        "rows": len(df),
        "training_rows": int((df["split"] == "training").sum()) if "split" in df.columns else 0,
        "validation_rows": int((df["split"] == "validation").sum()) if "split" in df.columns else 0,
        "start_datetime": df["datetime"].min(),
        "end_datetime": df["datetime"].max(),
    }
    for col in group_cols:
        summary[f"{col}_count"] = int(df[col].nunique(dropna=True)) if col in df.columns else 0
    return summary


def build_feature_compatibility(behavior_71471: pd.DataFrame, activity_622: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature_71471, feature_622 in FEATURE_MAPPING.items():
        available_71471 = feature_71471 in behavior_71471.columns
        available_622 = feature_622 in activity_622.columns
        rows.append(
            {
                "feature_71471": feature_71471,
                "feature_622": feature_622,
                "available_71471": available_71471,
                "available_622": available_622,
                "compatible": available_71471 and available_622,
            }
        )
    for feature in LABEL_ONLY_71471:
        rows.append(
            {
                "feature_71471": feature,
                "feature_622": "",
                "available_71471": feature in behavior_71471.columns,
                "available_622": False,
                "compatible": False,
            }
        )
    return pd.DataFrame(rows)


def _stats(series: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"mean": np.nan, "std": np.nan, "p50": np.nan, "p90": np.nan}
    return {
        "mean": float(values.mean()),
        "std": float(values.std(ddof=0)),
        "p50": float(values.quantile(0.50)),
        "p90": float(values.quantile(0.90)),
    }


def build_distribution_comparison(behavior_71471: pd.DataFrame, activity_622: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature_71471, feature_622 in FEATURE_MAPPING.items():
        if feature_71471 not in behavior_71471.columns or feature_622 not in activity_622.columns:
            continue
        stats_71471 = _stats(behavior_71471[feature_71471])
        stats_622 = _stats(activity_622[feature_622])
        rows.append(
            {
                "feature_71471": feature_71471,
                "feature_622": feature_622,
                "mean_71471": stats_71471["mean"],
                "mean_622": stats_622["mean"],
                "mean_ratio_71471_to_622": (
                    stats_71471["mean"] / stats_622["mean"]
                    if stats_622["mean"] and not np.isnan(stats_622["mean"])
                    else np.nan
                ),
                "p50_71471": stats_71471["p50"],
                "p50_622": stats_622["p50"],
                "p90_71471": stats_71471["p90"],
                "p90_622": stats_622["p90"],
            }
        )
    return pd.DataFrame(rows)


def decide_compatibility(feature_table: pd.DataFrame) -> dict[str, object]:
    comparable = int(feature_table["compatible"].sum())
    total = int(len(FEATURE_MAPPING))
    label_only_present = []
    for feature in LABEL_ONLY_71471:
        matches = feature_table.loc[feature_table["feature_71471"] == feature, "available_71471"]
        if not matches.empty and bool(matches.iloc[0]):
            label_only_present.append(feature)
    if comparable >= 10:
        decision = "compatible_as_auxiliary_behavior_track"
    elif comparable >= 5:
        decision = "partially_compatible"
    else:
        decision = "not_compatible"
    return {
        "comparable_features": comparable,
        "mapped_features": total,
        "compatibility_rate": comparable / total,
        "label_only_71471_features": ", ".join(label_only_present),
        "decision": decision,
    }


def write_compatibility_report(
    behavior_71471: pd.DataFrame,
    activity_622: pd.DataFrame,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_summary = pd.DataFrame(
        [
            summarize_dataset("AI Hub 71471 pig behavior", behavior_71471, ["farm_id", "channel"]),
            summarize_dataset("AI Hub 622 activity", activity_622, ["facility_number", "chamber_number", "pen_number"]),
        ]
    )
    feature_table = build_feature_compatibility(behavior_71471, activity_622)
    distribution = build_distribution_comparison(behavior_71471, activity_622)
    decision = pd.DataFrame([decide_compatibility(feature_table)])

    dataset_summary.to_csv(output_dir / "dataset_summary.csv", index=False)
    feature_table.to_csv(output_dir / "feature_compatibility.csv", index=False)
    distribution.to_csv(output_dir / "feature_distribution_comparison.csv", index=False)
    decision.to_csv(output_dir / "compatibility_decision.csv", index=False)

    report_path = output_dir / "aihub_71471_622_compatibility_report.md"
    compatible_features = feature_table[feature_table["compatible"]]
    report_lines = [
        "# AI Hub 71471 - 622 행동량 트랙 호환성 비교",
        "",
        "## 결론",
        "",
        "`71471`은 `622`와 완전히 같은 데이터는 아니지만, 행동량 보조 검증 트랙으로는 사용할 수 있습니다.",
        "다만 `71471`의 `ESTRUS`/`INJECTION` 계열은 모델 입력이 아니라 평가/설명 라벨로만 유지해야 합니다.",
        "",
        "## 호환성 판단",
        "",
        dataframe_to_markdown(decision),
        "",
        "## 데이터셋 요약",
        "",
        dataframe_to_markdown(dataset_summary),
        "",
        "## 호환 가능한 feature",
        "",
        dataframe_to_markdown(compatible_features[["feature_71471", "feature_622"]]),
        "",
        "## 전체 feature 매핑",
        "",
        dataframe_to_markdown(feature_table),
        "",
        "## 주요 분포 비교",
        "",
        dataframe_to_markdown(distribution.round(4)),
        "",
        "## 다음 작업",
        "",
        "- 71471 전용 행동 baseline을 별도로 만들고, `ESTRUS=Y` 구간이 정상 행동 패턴에서 얼마나 벗어나는지 평가합니다.",
        "- 71471과 622는 같은 농장/돈방이 아니므로 한 모델에 무리하게 섞기보다 보조 검증 트랙으로 유지합니다.",
        "- 대용량 원천 이미지/영상은 지금 단계에서는 받지 않습니다. 현재 keypoints 라벨만으로 행동 시계열 검증이 가능합니다.",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare 71471 and 622 behavior-track compatibility.")
    parser.add_argument("--aihub-71471", default="data/processed/aihub_71471_behavior_timeseries_10min.csv")
    parser.add_argument("--aihub-622", default="data/processed/aihub_622_activity_timeseries_10min.csv")
    parser.add_argument("--output-dir", default="artifacts/aihub_71471_compatibility")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    behavior_71471 = load_timeseries(args.aihub_71471)
    activity_622 = load_timeseries(args.aihub_622)
    report_path = write_compatibility_report(behavior_71471, activity_622, Path(args.output_dir))
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
