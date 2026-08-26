"""Create train/validation overview charts for a cleaned baseline model."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from tensorflow import keras

from pigproject.bioenergy_report import dataframe_to_markdown, load_window_metadata
from pigproject.detect import confirm_consecutive, reconstruction_error


def build_split_table(
    artifact_dir: str | Path,
    seq_len: int = 24,
    model_name: str = "best_model.keras",
) -> pd.DataFrame:
    artifacts = Path(artifact_dir)
    model = keras.models.load_model(artifacts / model_name)
    threshold = float(np.load(artifacts / "threshold.npy"))

    frames = []
    for split in ["train", "val"]:
        X = np.load(artifacts / f"X_{split}.npy")
        metadata = load_window_metadata(artifacts / f"bioenergy_{split}_scaled.csv", seq_len=seq_len)
        errors = reconstruction_error(model, X)
        raw_flags = errors > threshold
        confirmed_flags = confirm_consecutive(raw_flags, consecutive_required=3)
        if len(metadata) != len(errors):
            raise ValueError(f"{split} metadata/errors length mismatch: {len(metadata)} != {len(errors)}")
        metadata = metadata.copy()
        metadata["split"] = split
        metadata["reconstruction_error"] = errors
        metadata["threshold"] = threshold
        metadata["raw_anomaly"] = raw_flags
        metadata["confirmed_anomaly"] = confirmed_flags
        frames.append(metadata)
    return pd.concat(frames, ignore_index=True)


def draw_train_val_scatter(table: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1600, 920
    margin_l, margin_r, margin_t, margin_b = 105, 70, 85, 125
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    ordered = table.sort_values(["split", "dataset_key", "chamber_number", "start_datetime"]).reset_index(drop=True)
    errors = ordered["reconstruction_error"].to_numpy(dtype=float)
    threshold = float(ordered["threshold"].iloc[0])
    min_y = min(float(errors.min()), threshold)
    max_y = max(float(errors.max()), threshold)
    pad = max((max_y - min_y) * 0.12, 0.05)
    y0, y1 = min_y - pad, max_y + pad

    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    train_count = int((ordered["split"] == "train").sum())
    val_count = int((ordered["split"] == "val").sum())
    raw_count = int(ordered["raw_anomaly"].sum())
    confirmed_count = int(ordered["confirmed_anomaly"].sum())

    draw.text((margin_l, 30), "Clean Baseline Train + Validation Anomaly Score Scatter", fill="#222222", font=font)
    draw.text(
        (margin_l, 53),
        f"train={train_count}, validation={val_count}, threshold={threshold:.6f}, raw={raw_count}, confirmed={confirmed_count}",
        fill="#555555",
        font=font,
    )
    draw.line((margin_l, margin_t + plot_h, margin_l + plot_w, margin_t + plot_h), fill="#333333", width=2)
    draw.line((margin_l, margin_t, margin_l, margin_t + plot_h), fill="#333333", width=2)

    for frac in np.linspace(0, 1, 5):
        yy = margin_t + plot_h - frac * plot_h
        value = y0 + frac * (y1 - y0)
        draw.line((margin_l, yy, margin_l + plot_w, yy), fill="#e6e0d8", width=1)
        draw.text((margin_l - 82, yy - 6), f"{value:.2f}", fill="#555555", font=font)

    threshold_y = margin_t + plot_h - ((threshold - y0) / (y1 - y0)) * plot_h
    draw.line((margin_l, threshold_y, margin_l + plot_w, threshold_y), fill="#d24c34", width=3)
    draw.text((margin_l + plot_w - 116, threshold_y - 18), "threshold", fill="#d24c34", font=font)

    split_start_indices = ordered.groupby("split", sort=False).head(1).index.tolist()
    for idx in split_start_indices[1:]:
        xx = margin_l + (idx / max(len(ordered) - 1, 1)) * plot_w
        draw.line((xx, margin_t, xx, margin_t + plot_h), fill="#6b6258", width=2)
        draw.text((xx + 8, margin_t + 8), "validation starts", fill="#6b6258", font=font)

    n = max(len(ordered), 1)
    for idx, row in ordered.iterrows():
        xx = margin_l + (idx / max(n - 1, 1)) * plot_w
        yy = margin_t + plot_h - ((float(row["reconstruction_error"]) - y0) / (y1 - y0)) * plot_h
        if bool(row["confirmed_anomaly"]):
            fill = "#d24c34"
            radius = 6
        elif bool(row["raw_anomaly"]):
            fill = "#f0a13a"
            radius = 6
        elif row["split"] == "train":
            fill = "#2e78b7"
            radius = 4
        else:
            fill = "#2f9d68"
            radius = 5
        draw.ellipse((xx - radius, yy - radius, xx + radius, yy + radius), fill=fill, outline="#ffffff")

    legend_x = margin_l
    legend_y = height - 76
    legend = [
        ("train normal", "#2e78b7"),
        ("validation normal", "#2f9d68"),
        ("raw anomaly", "#f0a13a"),
        ("confirmed anomaly", "#d24c34"),
    ]
    for label, color in legend:
        draw.ellipse((legend_x, legend_y, legend_x + 14, legend_y + 14), fill=color, outline="#ffffff")
        draw.text((legend_x + 22, legend_y + 2), label, fill="#333333", font=font)
        legend_x += 190

    draw.text((margin_l, height - 42), "x-axis: train windows first, validation windows second", fill="#555555", font=font)
    draw.text((width - 260, height - 42), "y-axis: reconstruction error", fill="#555555", font=font)
    image.save(output, "JPEG", quality=92)
    return output


def write_overview_report(table: pd.DataFrame, output_path: str | Path, scatter_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    by_split = (
        table.groupby("split")["reconstruction_error"]
        .agg(["count", "min", "median", "mean", "max"])
        .reset_index()
        .round(6)
    )
    lines = [
        "# Clean Baseline Train + Validation Overview",
        "",
        f"- Scatter: `{scatter_path}`",
        f"- Threshold: `{float(table['threshold'].iloc[0]):.6f}`",
        f"- Train windows: `{int((table['split'] == 'train').sum())}`",
        f"- Validation windows: `{int((table['split'] == 'val').sum())}`",
        f"- Raw anomalies: `{int(table['raw_anomaly'].sum())}`",
        f"- Confirmed anomalies: `{int(table['confirmed_anomaly'].sum())}`",
        "",
        "## Split Summary",
        "",
        dataframe_to_markdown(by_split),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def create_overview(artifact_dir: str | Path, seq_len: int = 24, model_name: str = "best_model.keras") -> dict[str, Path]:
    artifacts = Path(artifact_dir)
    table = build_split_table(artifacts, seq_len=seq_len, model_name=model_name)
    table_path = artifacts / "bioenergy_train_val_detection_windows.csv"
    scatter_path = artifacts / "bioenergy_train_val_error_scatter.jpg"
    report_path = artifacts / "bioenergy_train_val_overview.md"
    table.to_csv(table_path, index=False)
    draw_train_val_scatter(table, scatter_path)
    write_overview_report(table, report_path, scatter_path)
    return {"table": table_path, "scatter": scatter_path, "report": report_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create train/validation overview charts for bio-energy baseline.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--model-name", default="best_model.keras")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = create_overview(args.artifact_dir, seq_len=args.seq_len, model_name=args.model_name)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
