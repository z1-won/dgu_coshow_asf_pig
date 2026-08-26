"""Draw temperature timelines from cleaned bio-energy baseline data."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


TEMP_COLUMNS = [
    "T_mean",
    "rectal_temperature_mean",
    "head_temperature_mean",
    "neck_temperature_mean",
    "back_temperature_mean",
]

TEMP_LABELS = {
    "T_mean": "barn temp",
    "rectal_temperature_mean": "rectal temp",
    "head_temperature_mean": "head temp",
    "neck_temperature_mean": "neck temp",
    "back_temperature_mean": "back temp",
}

TEMP_COLORS = {
    "T_mean": "#6b6258",
    "rectal_temperature_mean": "#d24c34",
    "head_temperature_mean": "#2e78b7",
    "neck_temperature_mean": "#2f9d68",
    "back_temperature_mean": "#7c5fb3",
}


def _scale(value: float, min_value: float, max_value: float, size: int) -> float:
    if max_value == min_value:
        return size / 2
    return ((value - min_value) / (max_value - min_value)) * size


def _draw_polyline(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, width: int = 3) -> None:
    if len(points) < 2:
        for x, y in points:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=fill)
        return
    draw.line(points, fill=fill, width=width, joint="curve")
    for x, y in points:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=fill, outline="#ffffff")


def draw_temperature_timeline(
    df: pd.DataFrame,
    output_path: str | Path,
    title: str,
    dataset_key: str | int | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = df.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    if dataset_key is not None:
        data = data[data["dataset_key"].astype(str).str.replace(".0", "", regex=False) == str(dataset_key)]
    data = data.dropna(subset=["datetime"]).sort_values(["dataset_key", "chamber_number", "datetime"])

    width, height = 1700, 1050
    margin_l, margin_r, margin_t, margin_b = 115, 65, 90, 130
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    values = data[TEMP_COLUMNS].to_numpy(dtype=float)
    min_y = float(np.nanmin(values))
    max_y = float(np.nanmax(values))
    min_y = min(min_y, 25.0)
    max_y = max(max_y, 41.0)
    pad = max((max_y - min_y) * 0.08, 0.5)
    min_y -= pad
    max_y += pad
    min_t = data["datetime"].min()
    max_t = data["datetime"].max()
    total_seconds = max((max_t - min_t).total_seconds(), 1)

    draw.text((margin_l, 28), title, fill="#222222", font=font)
    draw.text(
        (margin_l, 52),
        "x-axis=time, y-axis=temperature(C). One line segment is drawn within each dataset/chamber group.",
        fill="#555555",
        font=font,
    )
    draw.rectangle((margin_l, margin_t, margin_l + plot_w, margin_t + plot_h), outline="#333333", width=2)

    for frac in np.linspace(0, 1, 6):
        yy = margin_t + plot_h - frac * plot_h
        value = min_y + frac * (max_y - min_y)
        draw.line((margin_l, yy, margin_l + plot_w, yy), fill="#e6e0d8", width=1)
        draw.text((margin_l - 75, yy - 6), f"{value:.1f}C", fill="#555555", font=font)

    for threshold, label, color in [
        (40.5, "rectal fever ref 40.5C", "#d24c34"),
        (38.5, "surface/neck ref 38.5C", "#d88b2a"),
    ]:
        if min_y <= threshold <= max_y:
            yy = margin_t + plot_h - _scale(threshold, min_y, max_y, plot_h)
            draw.line((margin_l, yy, margin_l + plot_w, yy), fill=color, width=2)
            draw.text((margin_l + plot_w - 165, yy - 16), label, fill=color, font=font)

    for (_, _), group in data.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime")
        xs = [
            margin_l + ((dt - min_t).total_seconds() / total_seconds) * plot_w
            for dt in group["datetime"]
        ]
        for col in TEMP_COLUMNS:
            points = []
            for x, value in zip(xs, group[col]):
                if pd.isna(value):
                    continue
                y = margin_t + plot_h - _scale(float(value), min_y, max_y, plot_h)
                points.append((x, y))
            _draw_polyline(draw, points, TEMP_COLORS[col], width=2)

    legend_x = margin_l
    legend_y = height - 84
    for col in TEMP_COLUMNS:
        color = TEMP_COLORS[col]
        draw.line((legend_x, legend_y + 7, legend_x + 20, legend_y + 7), fill=color, width=4)
        draw.text((legend_x + 28, legend_y), TEMP_LABELS[col], fill="#333333", font=font)
        legend_x += 210

    draw.text((margin_l, height - 45), f"from {min_t} to {max_t}", fill="#555555", font=font)
    draw.text((width - 430, height - 45), "reference lines are design aids, not disease diagnosis", fill="#555555", font=font)
    image.save(output, "JPEG", quality=92)
    return output


def create_temperature_timelines(artifact_dir: str | Path) -> dict[str, Path]:
    artifacts = Path(artifact_dir)
    df = pd.read_csv(artifacts / "bioenergy_aggregated.csv", low_memory=False)
    outputs = {
        "all": draw_temperature_timeline(
            df,
            artifacts / "temperature_timeline_all.jpg",
            "Temperature Timeline - All Baseline Data",
        ),
        "71408": draw_temperature_timeline(
            df,
            artifacts / "temperature_timeline_71408.jpg",
            "Temperature Timeline - Dataset 71408",
            dataset_key=71408,
        ),
        "71763": draw_temperature_timeline(
            df,
            artifacts / "temperature_timeline_71763.jpg",
            "Temperature Timeline - Dataset 71763",
            dataset_key=71763,
        ),
    }
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw temperature timelines from clean baseline data.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_temperature_baseline")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = create_temperature_timelines(args.artifact_dir)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
