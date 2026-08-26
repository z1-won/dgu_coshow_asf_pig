"""Build frame-level activity features from normalized keypoint labels."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


BEHAVIOR_LABELS = [
    "Lying",
    "Standing",
    "Walking",
    "Running",
    "Eating",
    "Drinking",
    "Suckling",
    "Searching",
    "Scrubbing",
    "Urinating",
    "Defecating",
    "Sitting",
    "Resting",
    "Parturition",
]

ACTIVE_LABELS = {"Walking", "Running", "Searching", "Scrubbing", "Eating", "Drinking"}
REST_LABELS = {"Lying", "Resting", "Sitting"}

GROUP_COLUMNS = [
    "split",
    "facility_number",
    "chamber_number",
    "pen_number",
    "clip_name",
    "source_video",
    "datetime",
    "frame_id",
]

RAW_SUM_COLUMNS = [
    "point_annotation_count",
    "total_keypoints",
    "sum_center_x",
    "sum_center_y",
    "sum_center_x2",
    "sum_center_y2",
    "sum_span_x",
    "sum_span_y",
]


def prepare_points(points: pd.DataFrame) -> pd.DataFrame:
    points = points.copy()
    points["label"] = points["label"].fillna("Unknown")
    points["datetime"] = pd.to_datetime(points["datetime"], errors="coerce")
    points["source_video"] = points["source_video"].fillna("")
    points["point_count"] = pd.to_numeric(points["point_count"], errors="coerce").fillna(0)
    for col in ["center_x", "center_y", "span_x", "span_y"]:
        points[col] = pd.to_numeric(points[col], errors="coerce").fillna(0)
    points["center_x2"] = np.square(points["center_x"])
    points["center_y2"] = np.square(points["center_y"])
    return points


def aggregate_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    points = chunk[chunk["annotation_type"] == "points"].copy()
    if points.empty:
        return pd.DataFrame()
    points = prepare_points(points)

    base = (
        points.groupby(GROUP_COLUMNS, dropna=False)
        .agg(
            point_annotation_count=("label", "size"),
            total_keypoints=("point_count", "sum"),
            sum_center_x=("center_x", "sum"),
            sum_center_y=("center_y", "sum"),
            sum_center_x2=("center_x2", "sum"),
            sum_center_y2=("center_y2", "sum"),
            sum_span_x=("span_x", "sum"),
            sum_span_y=("span_y", "sum"),
            max_span_x=("span_x", "max"),
            max_span_y=("span_y", "max"),
        )
        .reset_index()
    )

    counts = (
        points.groupby(GROUP_COLUMNS + ["label"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    counts.columns = [str(col) for col in counts.columns]
    return base.merge(counts, on=GROUP_COLUMNS, how="left")


def combine_partials(partials: list[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(partials, ignore_index=True)
    label_cols = [
        col
        for col in combined.columns
        if col not in GROUP_COLUMNS and col not in RAW_SUM_COLUMNS and col not in {"max_span_x", "max_span_y"}
    ]
    agg_spec = {col: "sum" for col in RAW_SUM_COLUMNS}
    agg_spec.update({"max_span_x": "max", "max_span_y": "max"})
    agg_spec.update({col: "sum" for col in label_cols})
    return combined.groupby(GROUP_COLUMNS, dropna=False).agg(agg_spec).reset_index()


def finalize_activity(merged: pd.DataFrame) -> pd.DataFrame:
    n = merged["point_annotation_count"].replace(0, np.nan)
    merged["mean_center_x"] = merged["sum_center_x"] / n
    merged["mean_center_y"] = merged["sum_center_y"] / n
    merged["mean_span_x"] = merged["sum_span_x"] / n
    merged["mean_span_y"] = merged["sum_span_y"] / n
    merged["std_center_x"] = np.sqrt(
        ((merged["sum_center_x2"] / n) - np.square(merged["mean_center_x"])).clip(lower=0)
    ).fillna(0)
    merged["std_center_y"] = np.sqrt(
        ((merged["sum_center_y2"] / n) - np.square(merged["mean_center_y"])).clip(lower=0)
    ).fillna(0)

    for label in BEHAVIOR_LABELS:
        if label not in merged.columns:
            merged[label] = 0
        count_col = f"{label.lower()}_count"
        ratio_col = f"{label.lower()}_ratio"
        merged[count_col] = merged[label].fillna(0).astype(int)
        merged[ratio_col] = (merged[count_col] / n).fillna(0)

    active_count_cols = [f"{label.lower()}_count" for label in ACTIVE_LABELS]
    rest_count_cols = [f"{label.lower()}_count" for label in REST_LABELS]
    merged["active_behavior_count"] = merged[active_count_cols].sum(axis=1)
    merged["rest_behavior_count"] = merged[rest_count_cols].sum(axis=1)
    merged["active_behavior_ratio"] = (merged["active_behavior_count"] / n).fillna(0)
    merged["rest_behavior_ratio"] = (merged["rest_behavior_count"] / n).fillna(0)

    merged = merged.sort_values(
        ["split", "facility_number", "pen_number", "clip_name", "frame_id"],
        na_position="last",
    ).reset_index(drop=True)
    merged["center_movement"] = (
        merged.groupby(["split", "facility_number", "pen_number", "clip_name"], dropna=False)[
            ["mean_center_x", "mean_center_y"]
        ]
        .diff()
        .pow(2)
        .sum(axis=1)
        .pow(0.5)
        .fillna(0)
    )
    merged["center_movement_norm"] = merged["center_movement"] / np.sqrt(2560.0**2 + 1944.0**2)

    feature_cols = [
        "point_annotation_count",
        "total_keypoints",
        "active_behavior_count",
        "rest_behavior_count",
        "active_behavior_ratio",
        "rest_behavior_ratio",
        "mean_center_x",
        "mean_center_y",
        "std_center_x",
        "std_center_y",
        "mean_span_x",
        "mean_span_y",
        "max_span_x",
        "max_span_y",
        "center_movement",
        "center_movement_norm",
    ]
    behavior_cols = []
    for label in BEHAVIOR_LABELS:
        behavior_cols.extend([f"{label.lower()}_count", f"{label.lower()}_ratio"])
    return merged[GROUP_COLUMNS + feature_cols + behavior_cols]


def build_activity_features(input_path: str | Path, chunksize: int = 200_000) -> pd.DataFrame:
    usecols = [
        "split",
        "facility_number",
        "chamber_number",
        "pen_number",
        "clip_name",
        "source_video",
        "annotation_type",
        "label",
        "frame_id",
        "datetime",
        "point_count",
        "center_x",
        "center_y",
        "span_x",
        "span_y",
    ]
    partials = []
    for chunk in pd.read_csv(input_path, usecols=lambda col: col in usecols, chunksize=chunksize):
        if "annotation_type" not in chunk.columns:
            raise ValueError("Input CSV must include annotation_type. Run pig-normalize on XML labels first.")
        partial = aggregate_chunk(chunk)
        if not partial.empty:
            partials.append(partial)

    if not partials:
        raise ValueError("No point annotations found. Activity features need keypoint point labels.")
    return finalize_activity(combine_partials(partials))


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    table = df.reset_index()
    table.columns = [str(col) for col in table.columns]
    rows = ["| " + " | ".join(table.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(table.columns)) + " |")
    for _, row in table.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def summarize_activity(activity: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_cols = [
        "point_annotation_count",
        "active_behavior_ratio",
        "rest_behavior_ratio",
        "center_movement",
        "mean_span_x",
        "mean_span_y",
    ]
    lines = [
        "# 행동량 Feature 생성 보고서",
        "",
        f"- 전체 프레임 행 수: `{len(activity)}`",
        f"- Training 행 수: `{int((activity['split'] == 'training').sum())}`",
        f"- Validation 행 수: `{int((activity['split'] == 'validation').sum())}`",
        "",
        "## 돈방/pen별 프레임 수",
        "",
        dataframe_to_markdown(activity.groupby(["facility_number", "pen_number"]).size().to_frame("frame_count")),
        "",
        "## 핵심 feature 요약",
        "",
        dataframe_to_markdown(activity[summary_cols].describe().round(3)),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build activity features from keypoint labels.")
    parser.add_argument("--input", required=True, help="Normalized keypoint feature CSV from pig-normalize.")
    parser.add_argument("--output", default="data/processed/activity_features.csv")
    parser.add_argument("--report", default="artifacts/activity_feature_report.md")
    parser.add_argument("--chunksize", type=int, default=200_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    activity = build_activity_features(args.input, chunksize=args.chunksize)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    activity.to_csv(output, index=False)
    report = summarize_activity(activity, args.report)
    print(f"activity_features: {output} ({len(activity)} rows)")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
