"""Convert PigTrack/YOLO tracking boxes into movement features.

Expected input is one row per detected pig box:
`frame, track_id, x, y, w, h, conf` with optional `fps`, `pen_id`,
`source_video`, `frame_width`, `frame_height`, and `timestamp`.

This module is intentionally detector-agnostic. It accepts the spreadsheet-like
output shown by the team and produces reusable activity features before the
real CSV export exists in the project.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

REQUIRED_COLUMNS = {"frame", "track_id", "x", "y", "w", "h", "conf"}
DEFAULT_INPUT = "data/templates/cv_tracking_results_template.csv"
DEFAULT_OUTPUT_DIR = "artifacts/cv_tracking_features"
DEFAULT_FRAME_FEATURES = "data/processed/cv_tracking_frame_features.csv"
DEFAULT_ACTIVITY_COMPAT = "data/processed/cv_tracking_activity_features.csv"


def load_tracking_boxes(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Tracking CSV missing required columns: {sorted(missing)}")
    out = df.copy()
    for col in ["frame", "track_id", "x", "y", "w", "h", "conf"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["frame", "track_id", "x", "y", "w", "h", "conf"])
    out["frame"] = out["frame"].astype(int)
    out["track_id"] = out["track_id"].astype(int).astype(str)
    if "source_video" not in out:
        out["source_video"] = "unknown_video"
    out["source_video"] = out["source_video"].fillna("unknown_video").astype(str)
    if "pen_id" not in out:
        out["pen_id"] = "unknown_pen"
    out["pen_id"] = out["pen_id"].fillna("unknown_pen").astype(str)
    if "fps" not in out:
        out["fps"] = np.nan
    out["fps"] = pd.to_numeric(out["fps"], errors="coerce")
    if "frame_width" not in out:
        out["frame_width"] = np.nan
    if "frame_height" not in out:
        out["frame_height"] = np.nan
    out["frame_width"] = pd.to_numeric(out["frame_width"], errors="coerce")
    out["frame_height"] = pd.to_numeric(out["frame_height"], errors="coerce")
    if "timestamp" not in out:
        out["timestamp"] = pd.NA
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    return out.sort_values(["source_video", "pen_id", "track_id", "frame"]).reset_index(drop=True)


def add_box_geometry(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["center_x"] = out["x"] + out["w"] / 2
    out["center_y"] = out["y"] + out["h"] / 2
    out["bbox_area"] = out["w"] * out["h"]
    diag = np.sqrt(np.square(out["frame_width"]) + np.square(out["frame_height"]))
    fallback_diag = np.sqrt(np.square(out["center_x"].max()) + np.square(out["center_y"].max()))
    out["frame_diagonal_px"] = diag.where(diag > 0, fallback_diag)
    return out


def add_track_motion(df: pd.DataFrame) -> pd.DataFrame:
    out = add_box_geometry(df)
    group_cols = ["source_video", "pen_id", "track_id"]
    out[["prev_center_x", "prev_center_y", "prev_frame"]] = out.groupby(group_cols)[["center_x", "center_y", "frame"]].shift(1)
    out["frame_delta"] = out["frame"] - out["prev_frame"]
    out["movement_px"] = np.sqrt(np.square(out["center_x"] - out["prev_center_x"]) + np.square(out["center_y"] - out["prev_center_y"]))
    out.loc[out["frame_delta"].le(0) | out["frame_delta"].isna(), "movement_px"] = np.nan
    out["movement_px_per_frame"] = out["movement_px"] / out["frame_delta"]
    out["movement_norm"] = out["movement_px"] / out["frame_diagonal_px"].replace(0, np.nan)
    out["movement_norm_per_frame"] = out["movement_px_per_frame"] / out["frame_diagonal_px"].replace(0, np.nan)
    out["speed_px_per_sec"] = out["movement_px_per_frame"] * out["fps"]
    out["is_low_motion"] = out["movement_px_per_frame"].fillna(0) < 5.0
    out["is_high_motion"] = out["movement_px_per_frame"].fillna(0) > 40.0
    return out


def build_track_summary(motion: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in motion.groupby(["source_video", "pen_id", "track_id"], dropna=False):
        source_video, pen_id, track_id = keys
        frame_span = int(group["frame"].max() - group["frame"].min() + 1) if not group.empty else 0
        observed = int(group["frame"].nunique())
        rows.append(
            {
                "source_video": source_video,
                "pen_id": pen_id,
                "track_id": track_id,
                "first_frame": int(group["frame"].min()),
                "last_frame": int(group["frame"].max()),
                "frames_observed": observed,
                "frame_span": frame_span,
                "track_coverage_ratio": observed / frame_span if frame_span else np.nan,
                "mean_conf": float(group["conf"].mean()),
                "min_conf": float(group["conf"].min()),
                "total_movement_px": float(group["movement_px"].sum(skipna=True)),
                "mean_movement_px_per_frame": float(group["movement_px_per_frame"].mean(skipna=True)),
                "p95_movement_px_per_frame": float(group["movement_px_per_frame"].quantile(0.95)) if group["movement_px_per_frame"].notna().any() else np.nan,
                "mean_speed_px_per_sec": float(group["speed_px_per_sec"].mean(skipna=True)),
                "low_motion_ratio": float(group["is_low_motion"].mean()),
                "high_motion_ratio": float(group["is_high_motion"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_video", "pen_id", "track_id"]).reset_index(drop=True)


def build_frame_features(motion: pd.DataFrame) -> pd.DataFrame:
    frame = (
        motion.groupby(["source_video", "pen_id", "frame"], dropna=False)
        .agg(
            detected_pigs=("track_id", "nunique"),
            mean_conf=("conf", "mean"),
            min_conf=("conf", "min"),
            center_movement=("movement_px", "sum"),
            center_movement_norm=("movement_norm", "sum"),
            mean_movement_px_per_frame=("movement_px_per_frame", "mean"),
            max_movement_px_per_frame=("movement_px_per_frame", "max"),
            low_motion_ratio=("is_low_motion", "mean"),
            high_motion_ratio=("is_high_motion", "mean"),
            mean_bbox_area=("bbox_area", "mean"),
            max_bbox_area=("bbox_area", "max"),
            mean_center_x=("center_x", "mean"),
            mean_center_y=("center_y", "mean"),
            std_center_x=("center_x", "std"),
            std_center_y=("center_y", "std"),
        )
        .reset_index()
    )
    frame[["std_center_x", "std_center_y"]] = frame[["std_center_x", "std_center_y"]].fillna(0.0)
    return frame.sort_values(["source_video", "pen_id", "frame"]).reset_index(drop=True)


def build_pen_summary(frame_features: pd.DataFrame, track_summary: pd.DataFrame) -> pd.DataFrame:
    frame_part = (
        frame_features.groupby(["source_video", "pen_id"], dropna=False)
        .agg(
            frames=("frame", "nunique"),
            mean_detected_pigs=("detected_pigs", "mean"),
            min_detected_pigs=("detected_pigs", "min"),
            mean_center_movement=("center_movement", "mean"),
            max_center_movement=("center_movement", "max"),
            mean_low_motion_ratio=("low_motion_ratio", "mean"),
            mean_high_motion_ratio=("high_motion_ratio", "mean"),
            mean_conf=("mean_conf", "mean"),
        )
        .reset_index()
    )
    track_part = (
        track_summary.groupby(["source_video", "pen_id"], dropna=False)
        .agg(
            tracks=("track_id", "nunique"),
            mean_track_coverage_ratio=("track_coverage_ratio", "mean"),
            lowest_track_coverage_ratio=("track_coverage_ratio", "min"),
            most_active_track_movement=("total_movement_px", "max"),
            least_active_track_movement=("total_movement_px", "min"),
        )
        .reset_index()
    )
    return frame_part.merge(track_part, on=["source_video", "pen_id"], how="left")


def build_activity_compat(frame_features: pd.DataFrame, split: str = "external_cv", facility_number: int = 0, chamber_number: int = 0) -> pd.DataFrame:
    out = frame_features.copy()
    out["split"] = split
    out["facility_number"] = facility_number
    out["chamber_number"] = chamber_number
    out["pen_number"] = out["pen_id"].str.extract(r"(\d+)", expand=False).fillna("0").astype(int)
    # The existing activity resampler needs a datetime. Without real capture time,
    # use a deterministic synthetic timeline so frame ordering remains stable.
    base = pd.Timestamp("2026-01-01 00:00:00")
    out["datetime"] = base + pd.to_timedelta(out["frame"], unit="s")
    out["clip_name"] = out["source_video"]
    out["frame_id"] = out["frame"]
    out["point_annotation_count"] = out["detected_pigs"]
    out["total_keypoints"] = 0
    out["active_behavior_ratio"] = out["high_motion_ratio"]
    out["rest_behavior_ratio"] = out["low_motion_ratio"]
    out["mean_span_x"] = np.sqrt(out["mean_bbox_area"].clip(lower=0))
    out["mean_span_y"] = np.sqrt(out["mean_bbox_area"].clip(lower=0))
    columns = [
        "split",
        "facility_number",
        "chamber_number",
        "pen_number",
        "clip_name",
        "source_video",
        "datetime",
        "frame_id",
        "point_annotation_count",
        "total_keypoints",
        "active_behavior_ratio",
        "rest_behavior_ratio",
        "center_movement",
        "center_movement_norm",
        "mean_center_x",
        "mean_center_y",
        "std_center_x",
        "std_center_y",
        "mean_span_x",
        "mean_span_y",
        "max_movement_px_per_frame",
        "mean_conf",
        "detected_pigs",
    ]
    return out[columns]


def write_report(output_dir: Path, boxes: pd.DataFrame, motion: pd.DataFrame, track_summary: pd.DataFrame, frame_features: pd.DataFrame, pen_summary: pd.DataFrame) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    low_conf = int((boxes["conf"] < 0.7).sum())
    lines = [
        "# CV Tracking Feature 변환 리포트",
        "",
        f"- input detections: `{len(boxes)}`",
        f"- videos: `{boxes['source_video'].nunique()}`",
        f"- pens: `{boxes['pen_id'].nunique()}`",
        f"- tracks: `{track_summary['track_id'].nunique()}`",
        f"- frames: `{frame_features['frame'].nunique()}`",
        f"- low confidence boxes (<0.7): `{low_conf}`",
        "",
        "## Track별 요약",
        "",
        dataframe_to_markdown(track_summary.round(4)),
        "",
        "## Pen별 요약",
        "",
        dataframe_to_markdown(pen_summary.round(4)),
        "",
        "## 사용 방법",
        "",
        "- 팀원 결과 CSV는 `frame, track_id, x, y, w, h, conf` 컬럼만 있으면 변환 가능하다.",
        "- `fps`, `frame_width`, `frame_height`, `pen_id`, `source_video`가 있으면 속도와 정규화 이동량 해석이 더 좋아진다.",
        "- 현재 출력은 60프레임 샘플 검증/feature 설계용이며, 실제 모델 성능 주장은 더 긴 영상과 이벤트 라벨이 들어온 뒤 계산한다.",
    ]
    report = output_dir / "cv_tracking_feature_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_cv_tracking_features(
    input_path: str | Path = DEFAULT_INPUT,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    frame_output: str | Path = DEFAULT_FRAME_FEATURES,
    activity_output: str | Path = DEFAULT_ACTIVITY_COMPAT,
    split: str = "external_cv",
    facility_number: int = 0,
    chamber_number: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    Path(frame_output).parent.mkdir(parents=True, exist_ok=True)
    Path(activity_output).parent.mkdir(parents=True, exist_ok=True)

    boxes = load_tracking_boxes(input_path)
    motion = add_track_motion(boxes)
    track_summary = build_track_summary(motion)
    frame_features = build_frame_features(motion)
    pen_summary = build_pen_summary(frame_features, track_summary)
    activity_compat = build_activity_compat(frame_features, split=split, facility_number=facility_number, chamber_number=chamber_number)

    motion.to_csv(output / "cv_tracking_motion_rows.csv", index=False)
    track_summary.to_csv(output / "cv_tracking_track_summary.csv", index=False)
    frame_features.to_csv(frame_output, index=False)
    frame_features.to_csv(output / "cv_tracking_frame_features.csv", index=False)
    pen_summary.to_csv(output / "cv_tracking_pen_summary.csv", index=False)
    activity_compat.to_csv(activity_output, index=False)
    activity_compat.to_csv(output / "cv_tracking_activity_features.csv", index=False)
    write_report(output, boxes, motion, track_summary, frame_features, pen_summary)
    return motion, track_summary, frame_features, pen_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert YOLO/PigTrack tracking boxes into movement features.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--frame-output", default=DEFAULT_FRAME_FEATURES)
    parser.add_argument("--activity-output", default=DEFAULT_ACTIVITY_COMPAT)
    parser.add_argument("--split", default="external_cv")
    parser.add_argument("--facility-number", type=int, default=0)
    parser.add_argument("--chamber-number", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    motion, track_summary, frame_features, pen_summary = build_cv_tracking_features(
        input_path=args.input,
        output_dir=args.output_dir,
        frame_output=args.frame_output,
        activity_output=args.activity_output,
        split=args.split,
        facility_number=args.facility_number,
        chamber_number=args.chamber_number,
    )
    print(f"motion rows: {len(motion)}")
    print(f"tracks: {len(track_summary)}")
    print(f"frame features: {len(frame_features)}")
    print(f"pen summaries: {len(pen_summary)}")


if __name__ == "__main__":
    main()
