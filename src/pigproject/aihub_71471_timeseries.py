"""Normalize AI Hub 71471 pig keypoints and build behavior time series."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.aihub_71471_profile import load_71471_profile_rows


ACTION_LABELS = ["lying", "eating", "standing", "sitting"]
REST_LABELS = {"lying", "sitting"}
ACTIVE_LABELS = {"eating", "standing"}
ID_COLUMNS = ["split", "farm_id", "channel"]


def build_frame_datetime(rows: pd.DataFrame, fps: float = 30.0) -> pd.Series:
    start = pd.to_datetime(rows["record_date_hour"].astype(str), format="%Y%m%d%H", errors="coerce")
    timestamp = pd.to_numeric(rows["timestamp"], errors="coerce").fillna(0)
    return start + pd.to_timedelta(timestamp / fps, unit="s")


def normalize_71471_rows(input_dir: str | Path, fps: float = 30.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, errors = load_71471_profile_rows(input_dir)
    normalized = rows.copy()
    normalized["action_name"] = normalized["action_name"].str.lower().fillna("unknown")
    normalized["estrus"] = normalized["estrus"].fillna("unknown")
    normalized["datetime"] = build_frame_datetime(normalized, fps=fps)
    normalized["is_estrus"] = (normalized["estrus"] == "Y").astype(int)
    normalized["is_injected"] = (normalized["injection"] == "Y").astype(int)
    normalized["animal_count_proxy"] = 1

    numeric_cols = [
        "channel",
        "timestamp",
        "frame_from_name",
        "record_time",
        "image_width",
        "image_height",
        "visible_keypoints",
        "center_x",
        "center_y",
        "span_x",
        "span_y",
    ]
    for col in numeric_cols:
        normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    normalized = normalized.sort_values(
        ["split", "farm_id", "channel", "datetime", "member_name", "annotation_id"],
        na_position="last",
    ).reset_index(drop=True)
    return normalized, errors


def build_71471_frame_features(normalized: pd.DataFrame) -> pd.DataFrame:
    valid = normalized.dropna(subset=["datetime"]).copy()
    if valid.empty:
        raise ValueError("71471 rows do not contain usable datetime values.")

    group_cols = ID_COLUMNS + ["datetime", "member_name", "image_file_name", "record_date_hour", "clip_id"]
    base = (
        valid.groupby(group_cols, dropna=False)
        .agg(
            annotation_count=("annotation_id", "count"),
            visible_keypoints_mean=("visible_keypoints", "mean"),
            visible_keypoints_sum=("visible_keypoints", "sum"),
            mean_center_x=("center_x", "mean"),
            mean_center_y=("center_y", "mean"),
            mean_span_x=("span_x", "mean"),
            mean_span_y=("span_y", "mean"),
            max_span_x=("span_x", "max"),
            max_span_y=("span_y", "max"),
            estrus_positive_count=("is_estrus", "sum"),
            injected_count=("is_injected", "sum"),
        )
        .reset_index()
    )

    counts = (
        valid.groupby(group_cols + ["action_name"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    counts.columns = [str(col) for col in counts.columns]
    features = base.merge(counts, on=group_cols, how="left")
    for label in ACTION_LABELS:
        if label not in features.columns:
            features[label] = 0
        features[f"{label}_count"] = features[label].fillna(0).astype(int)
        features[f"{label}_ratio"] = (features[f"{label}_count"] / features["annotation_count"]).fillna(0)

    features["active_behavior_count"] = features[[f"{label}_count" for label in ACTIVE_LABELS]].sum(axis=1)
    features["rest_behavior_count"] = features[[f"{label}_count" for label in REST_LABELS]].sum(axis=1)
    features["active_behavior_ratio"] = (features["active_behavior_count"] / features["annotation_count"]).fillna(0)
    features["rest_behavior_ratio"] = (features["rest_behavior_count"] / features["annotation_count"]).fillna(0)
    features["estrus_ratio"] = (features["estrus_positive_count"] / features["annotation_count"]).fillna(0)
    features["injected_ratio"] = (features["injected_count"] / features["annotation_count"]).fillna(0)

    features = features.sort_values(ID_COLUMNS + ["datetime", "member_name"], na_position="last").reset_index(drop=True)
    features["center_movement_proxy"] = (
        features.groupby(ID_COLUMNS, dropna=False)[["mean_center_x", "mean_center_y"]]
        .diff()
        .pow(2)
        .sum(axis=1)
        .pow(0.5)
        .fillna(0)
    )
    image_width = pd.to_numeric(normalized.get("image_width", pd.Series(dtype=float)), errors="coerce").dropna()
    image_height = pd.to_numeric(normalized.get("image_height", pd.Series(dtype=float)), errors="coerce").dropna()
    max_width = float(image_width.max()) if not image_width.empty else 1920.0
    max_height = float(image_height.max()) if not image_height.empty else 1080.0
    diagonal = np.sqrt(np.square(max_width) + np.square(max_height))
    if not diagonal or np.isnan(diagonal):
        diagonal = np.sqrt(1920.0**2 + 1080.0**2)
    features["center_movement_norm"] = features["center_movement_proxy"] / diagonal

    output_cols = (
        group_cols
        + [
            "annotation_count",
            "visible_keypoints_mean",
            "visible_keypoints_sum",
            "mean_center_x",
            "mean_center_y",
            "mean_span_x",
            "mean_span_y",
            "max_span_x",
            "max_span_y",
            "center_movement_proxy",
            "center_movement_norm",
            "active_behavior_count",
            "rest_behavior_count",
            "active_behavior_ratio",
            "rest_behavior_ratio",
            "estrus_positive_count",
            "estrus_ratio",
            "injected_count",
            "injected_ratio",
        ]
    )
    for label in ACTION_LABELS:
        output_cols.extend([f"{label}_count", f"{label}_ratio"])
    return features[output_cols]


def build_71471_timeseries(frame_features: pd.DataFrame, freq: str = "10min") -> pd.DataFrame:
    frames = frame_features.copy()
    frames["datetime"] = pd.to_datetime(frames["datetime"], errors="coerce")
    frames = frames.dropna(subset=["datetime"])
    frames["time_bin"] = frames["datetime"].dt.floor(freq)

    count_cols = [
        "annotation_count",
        "visible_keypoints_sum",
        "active_behavior_count",
        "rest_behavior_count",
        "estrus_positive_count",
        "injected_count",
    ] + [f"{label}_count" for label in ACTION_LABELS]
    mean_cols = [
        "visible_keypoints_mean",
        "mean_center_x",
        "mean_center_y",
        "mean_span_x",
        "mean_span_y",
        "center_movement_norm",
    ]
    agg_spec = {col: "sum" for col in count_cols}
    agg_spec.update({col: "mean" for col in mean_cols})
    agg_spec.update({"max_span_x": "max", "max_span_y": "max", "center_movement_proxy": "sum"})

    time_series = (
        frames.groupby(ID_COLUMNS + ["time_bin"], dropna=False)
        .agg(agg_spec)
        .reset_index()
        .rename(columns={"time_bin": "datetime"})
        .sort_values(ID_COLUMNS + ["datetime"], na_position="last")
        .reset_index(drop=True)
    )

    frame_counts = (
        frames.groupby(ID_COLUMNS + ["time_bin"], dropna=False)
        .size()
        .reset_index(name="frame_count")
        .rename(columns={"time_bin": "datetime"})
    )
    time_series = time_series.merge(frame_counts, on=ID_COLUMNS + ["datetime"], how="left")

    denominator = time_series["annotation_count"].replace(0, np.nan)
    for label in ACTION_LABELS:
        time_series[f"{label}_ratio"] = (time_series[f"{label}_count"] / denominator).fillna(0)
    time_series["active_behavior_ratio"] = (time_series["active_behavior_count"] / denominator).fillna(0)
    time_series["rest_behavior_ratio"] = (time_series["rest_behavior_count"] / denominator).fillna(0)
    time_series["estrus_ratio"] = (time_series["estrus_positive_count"] / denominator).fillna(0)
    time_series["injected_ratio"] = (time_series["injected_count"] / denominator).fillna(0)
    return time_series


def model_feature_columns() -> list[str]:
    return [
        "annotation_count",
        "frame_count",
        "visible_keypoints_mean",
        "mean_center_x",
        "mean_center_y",
        "mean_span_x",
        "mean_span_y",
        "max_span_x",
        "max_span_y",
        "center_movement_proxy",
        "center_movement_norm",
        "active_behavior_ratio",
        "rest_behavior_ratio",
        "lying_ratio",
        "eating_ratio",
        "standing_ratio",
        "sitting_ratio",
    ]


def write_outputs(
    normalized: pd.DataFrame,
    errors: pd.DataFrame,
    frame_features: pd.DataFrame,
    time_series: pd.DataFrame,
    feature_output: Path,
    timeseries_output: Path,
    report_output: Path,
) -> Path:
    feature_output.parent.mkdir(parents=True, exist_ok=True)
    timeseries_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)

    normalized.to_csv(feature_output, index=False)
    frame_features.to_csv(feature_output.with_name(feature_output.stem + "_frame_features.csv"), index=False)
    time_series.to_csv(timeseries_output, index=False)
    pd.DataFrame({"feature": model_feature_columns()}).to_csv(
        timeseries_output.with_name(timeseries_output.stem + "_model_feature_columns.csv"),
        index=False,
    )
    errors.to_csv(report_output.with_name("aihub_71471_parse_errors.csv"), index=False)

    split_summary = (
        time_series.groupby("split", dropna=False)
        .agg(
            time_bins=("datetime", "count"),
            frames=("frame_count", "sum"),
            annotations=("annotation_count", "sum"),
            channels=("channel", "nunique"),
            estrus_ratio_mean=("estrus_ratio", "mean"),
        )
        .reset_index()
    )
    action_summary = (
        time_series.groupby("split", dropna=False)[[f"{label}_ratio" for label in ACTION_LABELS] + ["estrus_ratio"]]
        .mean()
        .reset_index()
    )
    report_lines = [
        "# AI Hub 71471 정규화 및 10분 행동 시계열",
        "",
        "## 산출물",
        "",
        f"- normalized annotations: `{feature_output}`",
        f"- frame features: `{feature_output.with_name(feature_output.stem + '_frame_features.csv')}`",
        f"- 10min time series: `{timeseries_output}`",
        f"- model feature columns: `{timeseries_output.with_name(timeseries_output.stem + '_model_feature_columns.csv')}`",
        "",
        "## 처리 요약",
        "",
        f"- normalized annotation rows: `{len(normalized)}`",
        f"- frame feature rows: `{len(frame_features)}`",
        f"- 10min time bins: `{len(time_series)}`",
        f"- skipped malformed JSON files: `{len(errors)}`",
        "",
        "## Split 요약",
        "",
        dataframe_to_markdown(split_summary),
        "",
        "## 평균 행동/발정 비율",
        "",
        dataframe_to_markdown(action_summary.round(4)),
        "",
        "## 모델 입력 원칙",
        "",
        "- `estrus_ratio`, `estrus_positive_count`, `injected_ratio`, `injected_count`는 평가/설명용 라벨로 유지합니다.",
        "- 모델 입력 후보 목록에서는 `estrus`와 `injection` 계열을 제외해 라벨 누수를 막습니다.",
        "- 71471은 체온/환경/ASF 라벨이 없으므로 ASF 직접 검증이 아니라 행동량 보강 검증으로 사용합니다.",
    ]
    report_output.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AI Hub 71471 normalized rows and behavior time series.")
    parser.add_argument("--input-dir", default="data/raw/aihub/71471")
    parser.add_argument("--feature-output", default="data/processed/aihub_71471_keypoint_features.csv")
    parser.add_argument("--timeseries-output", default="data/processed/aihub_71471_behavior_timeseries_10min.csv")
    parser.add_argument("--report", default="artifacts/aihub_71471_timeseries_report.md")
    parser.add_argument("--freq", default="10min")
    parser.add_argument("--fps", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    normalized, errors = normalize_71471_rows(args.input_dir, fps=args.fps)
    frame_features = build_71471_frame_features(normalized)
    time_series = build_71471_timeseries(frame_features, freq=args.freq)
    report = write_outputs(
        normalized=normalized,
        errors=errors,
        frame_features=frame_features,
        time_series=time_series,
        feature_output=Path(args.feature_output),
        timeseries_output=Path(args.timeseries_output),
        report_output=Path(args.report),
    )
    print(f"normalized: {args.feature_output} ({len(normalized)} rows)")
    print(f"timeseries: {args.timeseries_output} ({len(time_series)} rows)")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
