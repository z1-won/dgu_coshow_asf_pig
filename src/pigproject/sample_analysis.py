"""Analyze the provided AI Hub sample folder and create report artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


NUMERIC_COLUMNS = [
    "T",
    "RH",
    "CO2",
    "NH3",
    "breath_rate",
    "distance",
    "rectal_temperature",
    "back_temperature",
    "neck_temperature",
    "head_temperature",
    "evaporation",
    "ventilation_rate",
    "feedstuff_volume",
    "watersupply",
    "pig_manure",
    "sensible_heat",
    "latent_heat",
    "bbox_area_ratio",
]


def get_nested(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return np.nan
        current = current.get(key, np.nan)
    return current


def to_float(value: Any) -> float:
    try:
        if value is None:
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def infer_kind(path: Path) -> str:
    text = str(path)
    if "호흡량" in text:
        return "breathing"
    if "증발량" in text:
        return "evaporation"
    return "unknown"


def label_to_image_path(sample_dir: Path, label_path: Path) -> Path | None:
    rel = label_path.relative_to(sample_dir / "02.라벨링데이터")
    rel_text = str(rel)
    rel_text = rel_text.replace("증발량 데이터", "증발량 이미지")
    rel_text = rel_text.replace("호흡량 데이터", "호흡량 이미지")
    image_path = sample_dir / "01.원천데이터" / Path(rel_text).with_suffix(".png")
    return image_path if image_path.exists() else None


def image_size(path: Path | None) -> tuple[int | None, int | None]:
    if path is None:
        return None, None
    with Image.open(path) as image:
        return image.size


def parse_datetime(date_value: Any, time_value: Any) -> pd.Timestamp:
    text = f"{str(date_value).strip()}{str(time_value).strip().zfill(4)}"
    return pd.to_datetime(text, format="%y%m%d%H%M", errors="coerce")


def parse_label(sample_dir: Path, label_path: Path) -> dict[str, Any]:
    data = json.loads(label_path.read_text(encoding="utf-8"))
    image_path = label_to_image_path(sample_dir, label_path)
    width, height = image_size(image_path)
    info = data.get("ImageInfo", {})
    annotations = data.get("annotations", {})

    bbox = annotations.get("bbox")
    bbox_x = bbox_y = bbox_w = bbox_h = np.nan
    center_x = center_y = np.nan
    bbox_area_ratio = np.nan
    if isinstance(bbox, list) and len(bbox) == 4:
        bbox_x, bbox_y, bbox_w, bbox_h = [to_float(v) for v in bbox]
        center_x = bbox_x + bbox_w / 2
        center_y = bbox_y + bbox_h / 2
        if width and height:
            bbox_area_ratio = bbox_w * bbox_h / (width * height)

    keypoints = annotations.get("keypoint-top")
    if isinstance(keypoints, list) and len(keypoints) == 2:
        p1, p2 = keypoints
        if len(p1) == 2 and len(p2) == 2:
            center_x = (to_float(p1[0]) + to_float(p2[0])) / 2
            center_y = (to_float(p1[1]) + to_float(p2[1])) / 2

    available = annotations.get("available-area-bbox")
    available_area = np.nan
    if isinstance(available, list) and len(available) == 4 and width and height:
        available_area = to_float(available[2]) * to_float(available[3]) / (width * height)

    timestamp = str(info.get("timestamp", "")).strip()
    frame_number = int(timestamp) if timestamp.isdigit() else np.nan
    dt = parse_datetime(info.get("date"), info.get("time"))

    return {
        "kind": infer_kind(label_path),
        "label_path": str(label_path),
        "image_path": str(image_path) if image_path else "",
        "image_width": width,
        "image_height": height,
        "chamber_number": info.get("chamber-number"),
        "video_category": info.get("video-category"),
        "video_id": info.get("videoid"),
        "pig_classification": info.get("pig-classification"),
        "pig_number": info.get("pig-number", np.nan),
        "breathing_type": info.get("breathing-type", ""),
        "date": info.get("date"),
        "time": info.get("time"),
        "datetime": dt,
        "frame_number": frame_number,
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
        "latent_heat": to_float(data.get("latentHeat")),
        "bbox_x": bbox_x,
        "bbox_y": bbox_y,
        "bbox_w": bbox_w,
        "bbox_h": bbox_h,
        "center_x": center_x,
        "center_y": center_y,
        "bbox_area_ratio": bbox_area_ratio,
        "available_area_ratio": available_area,
    }


def load_sample_features(sample_dir: str | Path) -> pd.DataFrame:
    root = Path(sample_dir)
    label_root = root / "02.라벨링데이터"
    paths = sorted(label_root.rglob("*.json"))
    if not paths:
        raise FileNotFoundError(f"No label JSON files found under: {label_root}")
    rows = [parse_label(root, path) for path in paths]
    df = pd.DataFrame(rows)
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def draw_pig_map(df: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas_w, canvas_h = 1600, 1200
    margin = 70
    gap = 48
    panel_w = (canvas_w - 2 * margin - gap) // 2
    panel_h = (canvas_h - 2 * margin - gap - 80) // 2

    image = Image.new("RGB", (canvas_w, canvas_h), "#f7f4ee")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()

    draw.text((margin, 28), "Pig Position Map from AI Hub Sample", fill="#232323", font=title_font)
    draw.text((margin, 48), "Dots: bbox centers for evaporation labels, keypoint midpoints for breathing labels", fill="#555555", font=font)

    colors = {"evaporation": "#d65f3d", "breathing": "#2674b8", "unknown": "#666666"}
    chambers = sorted(df["chamber_number"].dropna().unique())
    positions = {
        chamber: (
            margin + (idx % 2) * (panel_w + gap),
            margin + 55 + (idx // 2) * (panel_h + gap),
        )
        for idx, chamber in enumerate(chambers[:4])
    }

    for chamber, (x0, y0) in positions.items():
        chamber_df = df[df["chamber_number"] == chamber]
        draw.rounded_rectangle((x0, y0, x0 + panel_w, y0 + panel_h), radius=16, fill="#fffdfa", outline="#d8d2c8", width=2)
        draw.text((x0 + 18, y0 + 14), f"Chamber {int(chamber)}", fill="#222222", font=title_font)
        draw.text((x0 + 18, y0 + 32), f"records: {len(chamber_df)}", fill="#666666", font=font)

        plot_x0, plot_y0 = x0 + 26, y0 + 62
        plot_w, plot_h = panel_w - 52, panel_h - 88
        draw.rectangle((plot_x0, plot_y0, plot_x0 + plot_w, plot_y0 + plot_h), fill="#f0eee8", outline="#c7bfb2")
        for gx in range(1, 4):
            xx = plot_x0 + plot_w * gx / 4
            draw.line((xx, plot_y0, xx, plot_y0 + plot_h), fill="#ded8ce")
        for gy in range(1, 4):
            yy = plot_y0 + plot_h * gy / 4
            draw.line((plot_x0, yy, plot_x0 + plot_w, yy), fill="#ded8ce")

        for _, row in chamber_df.iterrows():
            width = row.get("image_width") or 1920
            height = row.get("image_height") or 1080
            cx = row.get("center_x")
            cy = row.get("center_y")
            if pd.isna(cx) or pd.isna(cy):
                continue
            px = plot_x0 + max(0, min(1, cx / width)) * plot_w
            py = plot_y0 + max(0, min(1, cy / height)) * plot_h
            radius = 5
            if not pd.isna(row.get("bbox_area_ratio", np.nan)):
                radius = int(4 + min(12, row["bbox_area_ratio"] * 70))
            color = colors.get(row.get("kind"), colors["unknown"])
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color, outline="#ffffff")

    legend_y = canvas_h - 74
    draw.ellipse((margin, legend_y, margin + 18, legend_y + 18), fill=colors["evaporation"], outline="#ffffff")
    draw.text((margin + 28, legend_y + 2), "Evaporation bbox center", fill="#333333", font=font)
    draw.ellipse((margin + 260, legend_y, margin + 278, legend_y + 18), fill=colors["breathing"], outline="#ffffff")
    draw.text((margin + 288, legend_y + 2), "Breathing keypoint midpoint", fill="#333333", font=font)
    image.save(output, "JPEG", quality=92)
    return output


def stats_table(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    available = [col for col in columns if col in df.columns and df[col].notna().any()]
    if not available:
        return pd.DataFrame()
    return df[available].describe().T[["count", "mean", "std", "min", "max"]].round(3)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    table = df.reset_index()
    table.columns = [str(col) for col in table.columns]
    rows = ["| " + " | ".join(table.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(table.columns)) + " |")
    for _, row in table.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def write_report(df: pd.DataFrame, output_path: str | Path, map_path: str | Path, csv_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    counts_kind = df.groupby("kind").size().to_dict()
    counts_chamber = df.groupby("chamber_number").size().to_dict()
    counts_class = df.groupby("pig_classification").size().to_dict()
    numeric_stats = stats_table(df, NUMERIC_COLUMNS)
    missing = (df[NUMERIC_COLUMNS].isna().mean() * 100).round(1).sort_values(ascending=False)

    lines = [
        "# 샘플데이터 특징 분석 보고서",
        "",
        "## 1. 데이터 개요",
        "",
        f"- 샘플 루트: `/Users/bangjiwon/Downloads/Sample`",
        f"- 라벨 JSON 수: `{len(df)}`",
        f"- 매칭 이미지 수: `{int((df['image_path'] != '').sum())}`",
        f"- 분석 CSV: `{csv_path}`",
        f"- 돼지 맵 JPG: `{map_path}`",
        "",
        "## 2. 구성 분포",
        "",
        f"- 라벨 종류별 건수: `{counts_kind}`",
        f"- 돈방별 건수: `{counts_chamber}`",
        f"- 돼지 성장 단계별 건수: `{counts_class}`",
        "",
        "## 3. 주요 수치 특징",
        "",
    ]

    if not numeric_stats.empty:
        lines.append(dataframe_to_markdown(numeric_stats))
    else:
        lines.append("수치형 피처가 확인되지 않았습니다.")

    lines += [
        "",
        "## 4. 결측 특성",
        "",
        dataframe_to_markdown(missing.to_frame("missing_percent")),
        "",
        "## 5. 관찰 내용",
        "",
        "- `호흡량 데이터`는 `distance`, `breath-rate`, 체온 4종이 포함되어 LSTM Autoencoder 입력 피처에 바로 연결하기 좋습니다.",
        "- `증발량 데이터`는 체온/호흡수 대신 `evaporation`, `bbox`, 열량/분뇨량을 포함합니다. 돈방 환경 및 사양관리 설명 변수로 활용할 수 있습니다.",
        "- 샘플의 `timestamp`는 절대 시각이 아니라 프레임 번호 성격입니다. 시계열 학습에서는 `date + time + frame_number`를 정렬 키로 쓰고, 실제 장기 데이터에서는 API의 측정 시각 필드를 우선해야 합니다.",
        "- 현재 샘플은 24시간 정상 패턴 학습용이라기보다 필드 검증/특징 추출/시각화 검증에 적합합니다.",
        "",
        "## 6. AI Hub API 연결 시 반영할 점",
        "",
        "- API 수집 계층은 원천 파일 저장과 라벨 JSON 정규화를 분리합니다.",
        "- 라벨 종류별 스키마 차이를 유지하되, 모델 입력용 공통 테이블에는 `chamber_number`, `datetime`, 환경 4종, 활동 거리, 호흡수, 체온 4종, 사양관리 3종을 표준 컬럼으로 맞춥니다.",
        "- `증발량`처럼 모델 피처와 직접 일치하지 않는 라벨은 보조 분석 테이블 또는 추가 피처 후보로 관리합니다.",
        "- 대용량 수집에서는 파일 단위 generator와 chamber/date 파티션 저장을 적용하는 것이 좋습니다.",
    ]

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def analyze_sample(sample_dir: str | Path, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df = load_sample_features(sample_dir)
    csv_path = output / "sample_features.csv"
    map_path = output / "pig_map.jpg"
    report_path = output / "sample_feature_report.md"
    df.to_csv(csv_path, index=False)
    draw_pig_map(df, map_path)
    write_report(df, report_path, map_path, csv_path)
    return {"csv": csv_path, "map": map_path, "report": report_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze AI Hub sample folder and create map/report artifacts.")
    parser.add_argument("--sample-dir", required=True)
    parser.add_argument("--output-dir", default="artifacts/sample_analysis")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = analyze_sample(args.sample_dir, args.output_dir)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
