"""Resample frame-level activity features into regular chamber/pen time series."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ID_COLUMNS = ["split", "facility_number", "chamber_number", "pen_number"]


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    table = df.reset_index()
    table.columns = [str(col) for col in table.columns]
    rows = ["| " + " | ".join(table.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(table.columns)) + " |")
    for _, row in table.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def build_aggregation(columns: list[str]) -> dict[str, str]:
    aggregation: dict[str, str] = {}
    for col in columns:
        if col in ID_COLUMNS or col in {"datetime", "time_bin", "clip_name", "source_video", "frame_id"}:
            continue
        if col.endswith("_count") or col in {"point_annotation_count", "total_keypoints"}:
            aggregation[col] = "sum"
        elif col in {"center_movement", "center_movement_norm"}:
            aggregation[col] = "sum"
        elif col.startswith("max_"):
            aggregation[col] = "max"
        else:
            aggregation[col] = "mean"
    return aggregation


def resample_activity(input_path: str | Path, output_path: str | Path, freq: str = "10min") -> pd.DataFrame:
    df = pd.read_csv(input_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])
    df["time_bin"] = df["datetime"].dt.floor(freq)

    aggregation = build_aggregation(df.columns.tolist())
    resampled = (
        df.groupby(ID_COLUMNS + ["time_bin"], dropna=False)
        .agg(aggregation)
        .reset_index()
        .rename(columns={"time_bin": "datetime"})
        .sort_values(ID_COLUMNS + ["datetime"], na_position="last")
        .reset_index(drop=True)
    )

    frame_counts = (
        df.groupby(ID_COLUMNS + ["time_bin"], dropna=False)
        .size()
        .reset_index(name="frame_count")
        .rename(columns={"time_bin": "datetime"})
    )
    resampled = resampled.merge(frame_counts, on=ID_COLUMNS + ["datetime"], how="left")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    resampled.to_csv(output, index=False)
    return resampled


def write_report(resampled: pd.DataFrame, output_path: str | Path, freq: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 행동량 시계열 리샘플링 보고서",
        "",
        f"- 리샘플링 간격: `{freq}`",
        f"- 전체 시계열 행 수: `{len(resampled)}`",
        f"- Training 행 수: `{int((resampled['split'] == 'training').sum())}`",
        f"- Validation 행 수: `{int((resampled['split'] == 'validation').sum())}`",
        f"- 시간 범위: `{resampled['datetime'].min()}` ~ `{resampled['datetime'].max()}`",
        "",
        "## 돈방/pen별 time bin 수",
        "",
        dataframe_to_markdown(resampled.groupby(["facility_number", "pen_number"]).size().to_frame("time_bin_count")),
        "",
        "## 핵심 feature 요약",
        "",
        dataframe_to_markdown(
            resampled[
                [
                    "frame_count",
                    "point_annotation_count",
                    "active_behavior_ratio",
                    "rest_behavior_ratio",
                    "center_movement",
                    "mean_span_x",
                    "mean_span_y",
                ]
            ]
            .describe()
            .round(3)
        ),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resample activity features into regular time bins.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/processed/activity_timeseries_10min.csv")
    parser.add_argument("--report", default="artifacts/activity_timeseries_report.md")
    parser.add_argument("--freq", default="10min")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resampled = resample_activity(args.input, args.output, freq=args.freq)
    report = write_report(resampled, args.report, freq=args.freq)
    print(f"activity_timeseries: {args.output} ({len(resampled)} rows)")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
