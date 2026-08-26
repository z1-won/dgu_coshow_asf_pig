"""Normalize AI Hub sample/download folders into a common feature table."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.sample_analysis import load_sample_features, parse_datetime, to_float


MODEL_FEATURE_COLUMNS = [
    "chamber_number",
    "datetime",
    "frame_number",
    "pig_classification",
    "pig_number",
    "T",
    "RH",
    "CO2",
    "NH3",
    "distance",
    "breath_rate",
    "rectal_temperature",
    "back_temperature",
    "neck_temperature",
    "head_temperature",
    "ventilation_rate",
    "feedstuff_volume",
    "watersupply",
    "kind",
    "image_path",
    "label_path",
]


def parse_points(points: str) -> list[tuple[float, float]]:
    parsed = []
    for pair in points.split(";"):
        if not pair:
            continue
        x_text, y_text = pair.split(",", maxsplit=1)
        parsed.append((float(x_text), float(y_text)))
    return parsed


def parse_clip_metadata(name: str, source: str | None) -> dict[str, object]:
    text = source or name
    date_match = re.search(r"(20\d{6})_(\d{4})_(\d{4})", text)
    chamber_match = re.search(r"CH(\d+)", text)
    clip_match = re.search(r"P(\d+)_(\d+)_", text)
    pen_match = re.search(r"P(\d+)", text)
    start_dt = pd.NaT
    if date_match:
        start_dt = pd.to_datetime(date_match.group(1) + date_match.group(2), format="%Y%m%d%H%M", errors="coerce")
    facility_number = int(clip_match.group(1)) if clip_match else np.nan
    pen_number = int(clip_match.group(2)) if clip_match else (int(pen_match.group(1)) if pen_match else np.nan)
    chamber_number = int(chamber_match.group(1)) if chamber_match else facility_number
    return {
        "clip_name": name,
        "source_video": source or "",
        "clip_start_datetime": start_dt,
        "chamber_number": chamber_number,
        "facility_number": facility_number,
        "pen_number": pen_number,
    }


def rows_from_annotation_xml(xml_bytes: bytes, source_zip: Path, member_name: str, split: str) -> list[dict[str, object]]:
    root = ET.parse(BytesIO(xml_bytes)).getroot()
    source = root.findtext("./meta/task/source")
    original_width = root.findtext("./meta/task/original_size/width")
    original_height = root.findtext("./meta/task/original_size/height")
    clip_dir = str(Path(member_name).parent)
    meta = parse_clip_metadata(clip_dir, source)
    rows: list[dict[str, object]] = []

    for image in root.findall("image"):
        frame_id = int(image.attrib.get("id", 0))
        width = int(float(image.attrib.get("width") or original_width or 0))
        height = int(float(image.attrib.get("height") or original_height or 0))
        frame_datetime = meta["clip_start_datetime"]
        if not pd.isna(frame_datetime):
            frame_datetime = frame_datetime + pd.to_timedelta(frame_id, unit="s")

        for points in image.findall("points"):
            coords = parse_points(points.attrib.get("points", ""))
            if not coords:
                continue
            xs = [point[0] for point in coords]
            ys = [point[1] for point in coords]
            rows.append(
                {
                    **meta,
                    "split": split,
                    "source_zip": str(source_zip),
                    "member_name": member_name,
                    "annotation_type": "points",
                    "label": points.attrib.get("label", ""),
                    "occluded": points.attrib.get("occluded", ""),
                    "frame_id": frame_id,
                    "frame_name": image.attrib.get("name", ""),
                    "datetime": frame_datetime,
                    "image_width": width,
                    "image_height": height,
                    "point_count": len(coords),
                    "center_x": float(np.mean(xs)),
                    "center_y": float(np.mean(ys)),
                    "span_x": float(max(xs) - min(xs)),
                    "span_y": float(max(ys) - min(ys)),
                }
            )

        for box in image.findall("box"):
            xtl = float(box.attrib.get("xtl", np.nan))
            ytl = float(box.attrib.get("ytl", np.nan))
            xbr = float(box.attrib.get("xbr", np.nan))
            ybr = float(box.attrib.get("ybr", np.nan))
            rows.append(
                {
                    **meta,
                    "split": split,
                    "source_zip": str(source_zip),
                    "member_name": member_name,
                    "annotation_type": "box",
                    "label": box.attrib.get("label", ""),
                    "occluded": box.attrib.get("occluded", ""),
                    "frame_id": frame_id,
                    "frame_name": image.attrib.get("name", ""),
                    "datetime": frame_datetime,
                    "image_width": width,
                    "image_height": height,
                    "point_count": 0,
                    "center_x": (xtl + xbr) / 2,
                    "center_y": (ytl + ybr) / 2,
                    "span_x": xbr - xtl,
                    "span_y": ybr - ytl,
                }
            )
    return rows


def infer_split(path: Path) -> str:
    text = str(path)
    if "Validation" in text or "/2.Validation/" in text:
        return "validation"
    if "Training" in text or "/1.Training/" in text:
        return "training"
    return "unknown"


def get_nested(data: dict[str, object], *path: str) -> object:
    current: object = data
    for key in path:
        if not isinstance(current, dict):
            return np.nan
        current = current.get(key, np.nan)
    return current


def infer_dataset_key(path: Path) -> str:
    parts = set(path.parts)
    for key in ("622", "71408", "71763"):
        if key in parts:
            return key
    return ""


def infer_json_kind(member_name: str) -> str:
    if "호흡" in member_name or "breath" in member_name.lower():
        return "breathing"
    if "증발" in member_name or "evap" in member_name.lower():
        return "evaporation"
    if "weight" in member_name.lower() or "체중" in member_name:
        return "weight"
    return "unknown"


def row_from_json_label(data: dict[str, object], zip_path: Path, member_name: str) -> dict[str, object]:
    info = data.get("ImageInfo", {})
    annotations = data.get("annotations", {})
    text_info = data.get("TextInfo", {})
    if not isinstance(info, dict):
        info = {}
    if not isinstance(annotations, dict):
        annotations = {}
    if not isinstance(text_info, dict):
        text_info = {}

    keypoints = annotations.get("keypoint-top")
    center_x = center_y = np.nan
    if isinstance(keypoints, list) and len(keypoints) == 2:
        p1, p2 = keypoints
        if len(p1) == 2 and len(p2) == 2:
            center_x = (to_float(p1[0]) + to_float(p2[0])) / 2
            center_y = (to_float(p1[1]) + to_float(p2[1])) / 2

    timestamp = str(info.get("timestamp", "")).strip()
    frame_number = int(timestamp) if timestamp.isdigit() else np.nan

    return {
        "dataset_key": infer_dataset_key(zip_path),
        "split": infer_split(zip_path),
        "kind": infer_json_kind(member_name),
        "source_zip": str(zip_path),
        "member_name": member_name,
        "label_path": f"{zip_path}!{member_name}",
        "chamber_number": info.get("chamber-number"),
        "video_category": info.get("video-category"),
        "video_id": info.get("videoid"),
        "pig_classification": info.get("pig-classification"),
        "pig_number": info.get("pig-number", np.nan),
        "breathing_type": info.get("breathing-type", ""),
        "date": info.get("date"),
        "time": info.get("time"),
        "datetime": parse_datetime(info.get("date"), info.get("time")),
        "frame_number": frame_number,
        "weight": to_float(text_info.get("weight")),
        "T": to_float(get_nested(data, "SensorData", "T")),
        "RH": to_float(get_nested(data, "SensorData", "RH")),
        "CO2": to_float(get_nested(data, "SensorData", "CO2")),
        "NH3": to_float(get_nested(data, "SensorData", "NH3")),
        "breath_rate": to_float(data.get("breath-rate")),
        "distance": to_float(annotations.get("distance")),
        "rectal_temperature": to_float(get_nested(data, "TemperatureData", "rectal-temperature")),
        "back_temperature": to_float(get_nested(data, "TemperatureData", "back-temperature")),
        "neck_temperature": to_float(get_nested(data, "TemperatureData", "neck-temperature")),
        "head_temperature": to_float(get_nested(data, "TemperatureData", "head-temperature")),
        "evaporation": to_float(data.get("evaporation")),
        "ventilation_rate": to_float(get_nested(data, "FeedingAndManagementData", "ventilation-rate")),
        "feedstuff_volume": to_float(get_nested(data, "FeedingAndManagementData", "feedstuff_volume")),
        "watersupply": to_float(get_nested(data, "FeedingAndManagementData", "watersupply")),
        "pig_manure": to_float(data.get("pig-manure")),
        "sensible_heat": to_float(data.get("sensibleHeat")),
        "sensible_heat_kw": to_float(data.get("sensibleHeat(kW)")),
        "latent_heat": to_float(data.get("latentHeat")),
        "latent_heat_kw": to_float(data.get("latentHeat(kW)")),
        "center_x": center_x,
        "center_y": center_y,
    }


def load_aihub_json_zip_features(input_dir: str | Path) -> pd.DataFrame:
    root = Path(input_dir)
    rows: list[dict[str, object]] = []
    for zip_path in sorted(root.rglob("*.zip")):
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                if not member.endswith(".json"):
                    continue
                data = json.loads(archive.read(member).decode("utf-8"))
                rows.append(row_from_json_label(data, zip_path, member))
    if not rows:
        raise FileNotFoundError(f"No JSON label files found in zip files under: {input_dir}")
    return pd.DataFrame(rows)


def has_zip_member(input_dir: Path, suffix: str) -> bool:
    for zip_path in input_dir.rglob("*.zip"):
        with zipfile.ZipFile(zip_path) as archive:
            if any(member.endswith(suffix) for member in archive.namelist()):
                return True
    return False


def load_aihub_keypoint_xml_features(input_dir: str | Path) -> pd.DataFrame:
    root = Path(input_dir)
    rows: list[dict[str, object]] = []
    for zip_path in sorted(root.rglob("*.zip")):
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                if member.endswith("annotations.xml"):
                    rows.extend(
                        rows_from_annotation_xml(
                            archive.read(member),
                            source_zip=zip_path,
                            member_name=member,
                            split=infer_split(zip_path),
                        )
                    )
    if not rows:
        raise FileNotFoundError(f"No annotations.xml files found in zip files under: {input_dir}")
    return pd.DataFrame(rows)


def normalize_folder(input_dir: str | Path, output_path: str | Path) -> pd.DataFrame:
    input_root = Path(input_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if any(input_root.rglob("*.json")):
        df = load_sample_features(input_root)
        df = df.sort_values(["chamber_number", "datetime", "frame_number", "kind"], na_position="last")
    elif has_zip_member(input_root, ".json"):
        df = load_aihub_json_zip_features(input_root)
        df = df.sort_values(["split", "chamber_number", "datetime", "frame_number", "kind"], na_position="last")
    else:
        df = load_aihub_keypoint_xml_features(input_root)
        df = df.sort_values(["split", "chamber_number", "datetime", "frame_id", "label"], na_position="last")
    df.to_csv(output, index=False)
    return df


def write_model_ready_view(df: pd.DataFrame, output_path: str | Path) -> pd.DataFrame:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = [col for col in MODEL_FEATURE_COLUMNS if col in df.columns]
    if "kind" in df.columns:
        model_df = df[columns].copy()
        model_df = model_df[model_df["kind"] == "breathing"].reset_index(drop=True)
    else:
        model_df = df.copy()
        model_df = model_df[model_df["annotation_type"] == "points"].reset_index(drop=True)
    model_df.to_csv(output, index=False)
    return model_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize AI Hub folder into feature CSV files.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", default="data/processed/features.csv")
    parser.add_argument("--model-output", default="data/processed/model_features.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = normalize_folder(args.input_dir, args.output)
    model_df = write_model_ready_view(df, args.model_output)
    print(f"features: {args.output} ({len(df)} rows)")
    print(f"model_features: {args.model_output} ({len(model_df)} rows)")


if __name__ == "__main__":
    main()
