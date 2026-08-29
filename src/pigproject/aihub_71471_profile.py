"""Profile AI Hub 71471 pig keypoint labels."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


def infer_split(path: Path) -> str:
    text = str(path)
    if "Validation" in text or "/VL_" in text:
        return "validation"
    if "Training" in text or "/TL_" in text:
        return "training"
    return "unknown"


def parse_image_filename(filename: str) -> dict[str, object]:
    match = re.match(r"(?P<farm>[^_]+)_ch(?P<channel>\d+)_(?P<date>\d{10})_(?P<clip>\d+)_(?P<frame>\d+)\.jpg", filename)
    if not match:
        return {
            "farm_id_from_name": "",
            "channel": np.nan,
            "record_date_hour": "",
            "clip_id": "",
            "frame_from_name": np.nan,
        }
    groups = match.groupdict()
    return {
        "farm_id_from_name": groups["farm"],
        "channel": int(groups["channel"]),
        "record_date_hour": groups["date"],
        "clip_id": groups["clip"],
        "frame_from_name": int(groups["frame"]),
    }


def iter_71471_rows(input_dir: str | Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    root = Path(input_dir)
    rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for zip_path in sorted(root.rglob("*keypoints.zip")):
        split = infer_split(zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                if not member.endswith(".json"):
                    continue
                try:
                    data = json.loads(archive.read(member).decode("utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(
                        {
                            "source_zip": str(zip_path),
                            "member_name": member,
                            "error": f"{exc.msg} at line {exc.lineno} column {exc.colno}",
                        }
                    )
                    continue
                image = data.get("IMAGE", {})
                annotations = data.get("ANNOTATION_INFO", [])
                if not isinstance(image, dict) or not isinstance(annotations, list):
                    continue
                image_name = str(image.get("IMAGE_FILE_NAME", ""))
                parsed_name = parse_image_filename(image_name)
                timestamp = image.get("TIMESTAMP", np.nan)
                for annotation in annotations:
                    if not isinstance(annotation, dict):
                        continue
                    keypoints = annotation.get("KEYPOINTS", [])
                    xs: list[float] = []
                    ys: list[float] = []
                    visibility: list[int] = []
                    if isinstance(keypoints, list):
                        triples = [keypoints[index : index + 3] for index in range(0, len(keypoints), 3)]
                        for triple in triples:
                            if len(triple) != 3:
                                continue
                            x, y, visible = triple
                            xs.append(float(x))
                            ys.append(float(y))
                            visibility.append(int(visible))
                    rows.append(
                        {
                            "dataset_key": "71471",
                            "split": split,
                            "source_zip": str(zip_path),
                            "member_name": member,
                            "image_file_name": image_name,
                            "image_url": image.get("IMAGE_URL", ""),
                            "farm_id": image.get("FARMID", ""),
                            "farm_scale": image.get("FARMSCALE", np.nan),
                            "headcount": image.get("HEADCOUNT", np.nan),
                            "record_time": image.get("RECORD_TIME", np.nan),
                            "timestamp": timestamp,
                            "image_width": image.get("WIDTH", np.nan),
                            "image_height": image.get("HEIGHT", np.nan),
                            **parsed_name,
                            "annotation_id": annotation.get("ID", np.nan),
                            "category_name": annotation.get("CATEGORY_NAME", ""),
                            "action_name": annotation.get("ACTION_NAME", ""),
                            "estrus": annotation.get("ESTRUS", ""),
                            "injection": annotation.get("INJECTION", ""),
                            "num_keypoints": annotation.get("NUM_KEYPIONTS", len(visibility)),
                            "visible_keypoints": sum(1 for item in visibility if item > 0),
                            "center_x": float(np.mean(xs)) if xs else np.nan,
                            "center_y": float(np.mean(ys)) if ys else np.nan,
                            "span_x": float(max(xs) - min(xs)) if xs else np.nan,
                            "span_y": float(max(ys) - min(ys)) if ys else np.nan,
                        }
                    )
    if not rows:
        raise FileNotFoundError(f"No 71471 keypoint JSON files found under: {input_dir}")
    return rows, errors


def load_71471_profile_rows(input_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, errors = iter_71471_rows(input_dir)
    if not rows:
        raise FileNotFoundError(f"No valid 71471 keypoint JSON files found under: {input_dir}")
    return pd.DataFrame(rows), pd.DataFrame(errors)


def summarize_71471(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    split_summary = (
        df.groupby("split", dropna=False)
        .agg(
            annotations=("annotation_id", "count"),
            frames=("member_name", "nunique"),
            farms=("farm_id", "nunique"),
            channels=("channel", "nunique"),
            action_classes=("action_name", "nunique"),
            estrus_positive=("estrus", lambda values: int((values == "Y").sum())),
            estrus_negative=("estrus", lambda values: int((values == "N").sum())),
        )
        .reset_index()
    )
    action_summary = (
        df.groupby(["split", "action_name"], dropna=False)
        .size()
        .reset_index(name="annotations")
        .sort_values(["split", "annotations"], ascending=[True, False])
    )
    estrus_summary = (
        df.groupby(["split", "estrus"], dropna=False)
        .size()
        .reset_index(name="annotations")
        .sort_values(["split", "estrus"])
    )
    channel_summary = (
        df.groupby(["split", "farm_id", "channel"], dropna=False)
        .agg(
            annotations=("annotation_id", "count"),
            frames=("member_name", "nunique"),
            first_timestamp=("timestamp", "min"),
            last_timestamp=("timestamp", "max"),
        )
        .reset_index()
        .sort_values(["split", "farm_id", "channel"])
    )
    return {
        "split_summary": split_summary,
        "action_summary": action_summary,
        "estrus_summary": estrus_summary,
        "channel_summary": channel_summary,
    }


def write_profile_outputs(df: pd.DataFrame, errors: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = summarize_71471(df)
    row_path = output_dir / "aihub_71471_keypoint_rows.csv"
    df.to_csv(row_path, index=False)
    error_path = output_dir / "aihub_71471_parse_errors.csv"
    errors.to_csv(error_path, index=False)
    for name, summary in summaries.items():
        summary.to_csv(output_dir / f"{name}.csv", index=False)

    report_path = output_dir / "aihub_71471_profile_report.md"
    report_lines = [
        "# AI Hub 71471 돼지 keypoints 프로파일",
        "",
        "## 다운로드 검증",
        "",
        f"- annotation rows: `{len(df)}`",
        f"- frames: `{df['member_name'].nunique()}`",
        f"- source ZIPs: `{df['source_zip'].nunique()}`",
        f"- skipped malformed JSON files: `{len(errors)}`",
        "",
        "## Split 요약",
        "",
        dataframe_to_markdown(summaries["split_summary"]),
        "",
        "## 행동 라벨 분포",
        "",
        dataframe_to_markdown(summaries["action_summary"]),
        "",
        "## 발정 라벨 분포",
        "",
        dataframe_to_markdown(summaries["estrus_summary"]),
        "",
        "## 통합 판단",
        "",
        "- 71471은 `ACTION_NAME`, `ESTRUS`, `KEYPOINTS`를 제공하므로 행동 라벨 보강 후보로 사용할 수 있습니다.",
        "- 환경센서, 체온, ASF 임상 라벨은 없으므로 ASF 이상탐지의 직접 검증 데이터로 쓰면 안 됩니다.",
        "- 시간 정보는 이미지 파일명과 `TIMESTAMP` 중심이라, 622처럼 돈방 센서 시계열과 바로 결합하려면 전용 정규화/리샘플링 로직이 필요합니다.",
        "- 일부 JSON은 원천 라벨 문법 오류로 건너뛰며, 목록은 `aihub_71471_parse_errors.csv`에 기록합니다.",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile AI Hub 71471 pig keypoint labels.")
    parser.add_argument("--input-dir", default="data/raw/aihub/71471")
    parser.add_argument("--output-dir", default="artifacts/aihub_71471_profile")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df, errors = load_71471_profile_rows(args.input_dir)
    report_path = write_profile_outputs(df, errors, Path(args.output_dir))
    print(f"Wrote {report_path}")
    print(dataframe_to_markdown(summarize_71471(df)["split_summary"]))


if __name__ == "__main__":
    main()
