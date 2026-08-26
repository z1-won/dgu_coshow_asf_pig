"""Draw time vs combined-temperature window scatter plots."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


def _norm_dataset(value: object) -> str:
    text = str(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _scale(value: float, min_value: float, max_value: float, size: int) -> float:
    if min_value == max_value:
        return size / 2
    return ((value - min_value) / (max_value - min_value)) * size


def draw_window_scatter(
    df: pd.DataFrame,
    output_path: str | Path,
    title: str,
    dataset_key: str | int | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = df.copy()
    if dataset_key is not None:
        data = data[data["dataset_key"].map(_norm_dataset) == str(dataset_key)]
    data["end_datetime"] = pd.to_datetime(data["end_datetime"], errors="coerce")
    data = data.dropna(subset=["end_datetime"]).sort_values("end_datetime").reset_index(drop=True)

    width, height = 1600, 950
    margin_l, margin_r, margin_t, margin_b = 115, 70, 95, 130
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    y_values = data["pc1"].to_numpy(dtype=float)
    min_y, max_y = float(np.nanmin(y_values)), float(np.nanmax(y_values))
    pad_y = max((max_y - min_y) * 0.1, 0.1)
    min_y -= pad_y
    max_y += pad_y
    min_t = data["end_datetime"].min()
    max_t = data["end_datetime"].max()
    total_seconds = max((max_t - min_t).total_seconds(), 1)

    raw = data["raw_anomaly"].astype(str).str.lower().isin({"true", "1"})
    confirmed = data["confirmed_anomaly"].astype(str).str.lower().isin({"true", "1"})
    train_count = int((data["split"] == "train").sum())
    val_count = int((data["split"] == "val").sum())

    draw.text((margin_l, 30), title, fill="#222222", font=font)
    draw.text(
        (margin_l, 54),
        f"each dot=24-timestep window, train={train_count}, validation={val_count}, raw={int(raw.sum())}, confirmed={int(confirmed.sum())}",
        fill="#555555",
        font=font,
    )
    draw.text(
        (margin_l, 76),
        "x-axis=time, y-axis=PC1 combined temperature pattern score, not Celsius.",
        fill="#555555",
        font=font,
    )
    draw.rectangle((margin_l, margin_t, margin_l + plot_w, margin_t + plot_h), outline="#333333", width=2)

    for frac in np.linspace(0, 1, 5):
        yy = margin_t + plot_h - frac * plot_h
        value = min_y + frac * (max_y - min_y)
        draw.line((margin_l, yy, margin_l + plot_w, yy), fill="#e6e0d8", width=1)
        draw.text((margin_l - 78, yy - 6), f"{value:.2f}", fill="#555555", font=font)

    for idx, row in data.iterrows():
        seconds = (row["end_datetime"] - min_t).total_seconds()
        x = margin_l + (seconds / total_seconds) * plot_w
        y = margin_t + plot_h - _scale(float(row["pc1"]), min_y, max_y, plot_h)
        is_raw = str(row["raw_anomaly"]).lower() in {"true", "1"}
        is_confirmed = str(row["confirmed_anomaly"]).lower() in {"true", "1"}
        if is_confirmed:
            fill, radius = "#d24c34", 7
        elif is_raw:
            fill, radius = "#f0a13a", 7
        elif row["split"] == "train":
            fill, radius = "#2e78b7", 5
        else:
            fill, radius = "#2f9d68", 6
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline="#ffffff")

    legend_x = margin_l
    legend_y = height - 82
    for label, color in [
        ("train normal", "#2e78b7"),
        ("validation normal", "#2f9d68"),
        ("raw anomaly", "#f0a13a"),
        ("confirmed anomaly", "#d24c34"),
    ]:
        draw.ellipse((legend_x, legend_y, legend_x + 14, legend_y + 14), fill=color, outline="#ffffff")
        draw.text((legend_x + 22, legend_y + 2), label, fill="#333333", font=font)
        legend_x += 190

    draw.text((margin_l, height - 45), f"from {min_t} to {max_t}", fill="#555555", font=font)
    draw.text((width - 540, height - 45), "PC1 combines the selected temperature features across each 24-step window", fill="#555555", font=font)
    image.save(output, "JPEG", quality=92)
    return output


def create_window_scatters(artifact_dir: str | Path) -> dict[str, Path]:
    artifacts = Path(artifact_dir)
    df = pd.read_csv(artifacts / "bioenergy_pca_windows.csv", low_memory=False)
    return {
        "all": draw_window_scatter(
            df,
            artifacts / "temperature_window_pc1_scatter_all.jpg",
            "Temperature Window Scatter - All Baseline Data",
        ),
        "71408": draw_window_scatter(
            df,
            artifacts / "temperature_window_pc1_scatter_71408.jpg",
            "Temperature Window Scatter - Dataset 71408",
            dataset_key=71408,
        ),
        "71763": draw_window_scatter(
            df,
            artifacts / "temperature_window_pc1_scatter_71763.jpg",
            "Temperature Window Scatter - Dataset 71763",
            dataset_key=71763,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw time vs combined-temperature window scatter plots.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_temperature_baseline")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = create_window_scatters(args.artifact_dir)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
