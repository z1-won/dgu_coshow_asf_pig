"""Create detection reports for the bio-energy LSTM Autoencoder."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


def load_window_metadata(val_scaled_path: str | Path, seq_len: int) -> pd.DataFrame:
    df = pd.read_csv(val_scaled_path, low_memory=False)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    rows = []
    for _, group in df.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime").reset_index(drop=True)
        for start in range(len(group) - seq_len + 1):
            end = start + seq_len - 1
            rows.append(
                {
                    "dataset_key": group.loc[start, "dataset_key"],
                    "chamber_number": group.loc[start, "chamber_number"],
                    "start_datetime": group.loc[start, "datetime"],
                    "end_datetime": group.loc[end, "datetime"],
                    "window_start_index": start,
                    "window_end_index": end,
                }
            )
    return pd.DataFrame(rows)


def make_error_table(artifact_dir: str | Path, seq_len: int) -> pd.DataFrame:
    artifacts = Path(artifact_dir)
    errors = np.load(artifacts / "last_errors.npy")
    raw_flags = np.load(artifacts / "last_raw_flags.npy")
    confirmed_flags = np.load(artifacts / "last_confirmed_flags.npy")
    threshold = float(np.load(artifacts / "threshold.npy"))
    metadata = load_window_metadata(artifacts / "bioenergy_val_scaled.csv", seq_len=seq_len)

    if len(metadata) != len(errors):
        raise ValueError(f"Metadata/errors length mismatch: {len(metadata)} != {len(errors)}")

    metadata = metadata.copy()
    metadata["reconstruction_error"] = errors
    metadata["threshold"] = threshold
    metadata["raw_anomaly"] = raw_flags
    metadata["confirmed_anomaly"] = confirmed_flags
    metadata["error_over_threshold"] = metadata["reconstruction_error"] - threshold
    return metadata.sort_values("reconstruction_error", ascending=False).reset_index(drop=True)


def draw_histogram(errors: np.ndarray, threshold: float, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1400, 900
    margin_l, margin_r, margin_t, margin_b = 90, 50, 80, 110
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    bins = min(24, max(8, len(errors)))
    counts, edges = np.histogram(errors, bins=bins)
    max_count = max(int(counts.max()), 1)
    min_x, max_x = float(edges[0]), float(edges[-1])
    if min_x == max_x:
        max_x = min_x + 1.0

    draw.text((margin_l, 32), "Bio-energy Reconstruction Error Distribution", fill="#222222", font=font)
    draw.text((margin_l, 52), f"windows={len(errors)}, threshold={threshold:.6f}", fill="#555555", font=font)
    draw.line((margin_l, margin_t + plot_h, margin_l + plot_w, margin_t + plot_h), fill="#333333", width=2)
    draw.line((margin_l, margin_t, margin_l, margin_t + plot_h), fill="#333333", width=2)

    for idx, count in enumerate(counts):
        x0 = margin_l + idx * plot_w / bins
        x1 = margin_l + (idx + 1) * plot_w / bins - 4
        y1 = margin_t + plot_h
        bar_h = (count / max_count) * (plot_h - 20)
        y0 = y1 - bar_h
        draw.rectangle((x0, y0, x1, y1), fill="#2e78b7", outline="#ffffff")

    tx = margin_l + ((threshold - min_x) / (max_x - min_x)) * plot_w
    tx = max(margin_l, min(margin_l + plot_w, tx))
    draw.line((tx, margin_t, tx, margin_t + plot_h), fill="#d24c34", width=4)
    draw.text((tx + 8, margin_t + 8), "threshold", fill="#d24c34", font=font)

    draw.text((margin_l, height - 72), f"min={errors.min():.6f}", fill="#333333", font=font)
    draw.text((margin_l + 260, height - 72), f"median={np.median(errors):.6f}", fill="#333333", font=font)
    draw.text((margin_l + 560, height - 72), f"max={errors.max():.6f}", fill="#333333", font=font)
    image.save(output, "JPEG", quality=92)
    return output


def draw_scatter(table: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1500, 900
    margin_l, margin_r, margin_t, margin_b = 100, 70, 85, 125
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    ordered = table.sort_values(["dataset_key", "chamber_number", "start_datetime"]).reset_index(drop=True)
    errors = ordered["reconstruction_error"].to_numpy(dtype=float)
    threshold = float(ordered["threshold"].iloc[0])
    min_y = min(float(errors.min()), threshold)
    max_y = max(float(errors.max()), threshold)
    pad = max((max_y - min_y) * 0.12, 0.05)
    y0, y1 = min_y - pad, max_y + pad

    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text((margin_l, 32), "Bio-energy Anomaly Score Scatter", fill="#222222", font=font)
    draw.text(
        (margin_l, 54),
        f"each dot = one validation window, threshold={threshold:.6f}",
        fill="#555555",
        font=font,
    )
    draw.line((margin_l, margin_t + plot_h, margin_l + plot_w, margin_t + plot_h), fill="#333333", width=2)
    draw.line((margin_l, margin_t, margin_l, margin_t + plot_h), fill="#333333", width=2)

    for frac in np.linspace(0, 1, 5):
        yy = margin_t + plot_h - frac * plot_h
        value = y0 + frac * (y1 - y0)
        draw.line((margin_l, yy, margin_l + plot_w, yy), fill="#e6e0d8", width=1)
        draw.text((margin_l - 78, yy - 6), f"{value:.2f}", fill="#555555", font=font)

    threshold_y = margin_t + plot_h - ((threshold - y0) / (y1 - y0)) * plot_h
    draw.line((margin_l, threshold_y, margin_l + plot_w, threshold_y), fill="#d24c34", width=3)
    draw.text((margin_l + plot_w - 115, threshold_y - 18), "threshold", fill="#d24c34", font=font)

    n = max(len(ordered), 1)
    group_starts = ordered.groupby(["dataset_key", "chamber_number"], sort=False).head(1).index.tolist()
    for idx in group_starts[1:]:
        xx = margin_l + (idx / max(n - 1, 1)) * plot_w
        draw.line((xx, margin_t, xx, margin_t + plot_h), fill="#d8d1c8", width=1)

    for idx, row in ordered.iterrows():
        xx = margin_l + (idx / max(n - 1, 1)) * plot_w
        yy = margin_t + plot_h - ((float(row["reconstruction_error"]) - y0) / (y1 - y0)) * plot_h
        if bool(row["confirmed_anomaly"]):
            fill = "#d24c34"
            radius = 7
        elif bool(row["raw_anomaly"]):
            fill = "#f0a13a"
            radius = 6
        else:
            fill = "#2e78b7"
            radius = 5
        draw.ellipse((xx - radius, yy - radius, xx + radius, yy + radius), fill=fill, outline="#ffffff")

    legend_x = margin_l
    legend_y = height - 76
    legend = [("normal", "#2e78b7"), ("raw anomaly", "#f0a13a"), ("confirmed anomaly", "#d24c34")]
    for label, color in legend:
        draw.ellipse((legend_x, legend_y, legend_x + 14, legend_y + 14), fill=color, outline="#ffffff")
        draw.text((legend_x + 22, legend_y + 2), label, fill="#333333", font=font)
        legend_x += 170

    draw.text((margin_l, height - 42), "x-axis: validation windows ordered by dataset and chamber", fill="#555555", font=font)
    draw.text((width - 260, height - 42), "y-axis: reconstruction error", fill="#555555", font=font)

    image.save(output, "JPEG", quality=92)
    return output


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    table = df.copy()
    for col in ["start_datetime", "end_datetime"]:
        if col in table.columns:
            table[col] = table[col].astype(str)
    rows = ["| " + " | ".join(table.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(table.columns)) + " |")
    for _, row in table.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def write_report(
    table: pd.DataFrame,
    output_path: str | Path,
    histogram_path: str | Path,
    scatter_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    errors = table["reconstruction_error"].to_numpy()
    top = table.head(10)[
        [
            "dataset_key",
            "chamber_number",
            "start_datetime",
            "end_datetime",
            "reconstruction_error",
            "threshold",
            "raw_anomaly",
            "confirmed_anomaly",
        ]
    ].copy()
    top["reconstruction_error"] = top["reconstruction_error"].round(6)
    top["threshold"] = top["threshold"].round(6)

    by_group = table.groupby(["dataset_key", "chamber_number"])["reconstruction_error"].agg(["count", "mean", "max"]).round(6)

    lines = [
        "# Bio-energy LSTM Autoencoder Detection Report",
        "",
        f"- Histogram: `{histogram_path}`",
        f"- Scatter: `{scatter_path}`",
        f"- Windows: `{len(table)}`",
        f"- Threshold: `{float(table['threshold'].iloc[0]):.6f}`",
        f"- Raw anomalies: `{int(table['raw_anomaly'].sum())}`",
        f"- Confirmed anomalies: `{int(table['confirmed_anomaly'].sum())}`",
        "",
        "## Error Summary",
        "",
        f"- min: `{errors.min():.6f}`",
        f"- median: `{np.median(errors):.6f}`",
        f"- mean: `{errors.mean():.6f}`",
        f"- p95: `{np.percentile(errors, 95):.6f}`",
        f"- p99: `{np.percentile(errors, 99):.6f}`",
        f"- max: `{errors.max():.6f}`",
        "",
        "## Top Windows",
        "",
        dataframe_to_markdown(top),
        "",
        "## Group Summary",
        "",
        dataframe_to_markdown(by_group.reset_index()),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def create_report(artifact_dir: str | Path, seq_len: int = 24) -> dict[str, Path]:
    artifacts = Path(artifact_dir)
    table = make_error_table(artifacts, seq_len=seq_len)
    table_path = artifacts / "bioenergy_detection_windows.csv"
    histogram_path = artifacts / "bioenergy_error_distribution.jpg"
    scatter_path = artifacts / "bioenergy_error_scatter.jpg"
    report_path = artifacts / "bioenergy_detection_report.md"
    table.to_csv(table_path, index=False)
    draw_histogram(table["reconstruction_error"].to_numpy(), float(table["threshold"].iloc[0]), histogram_path)
    draw_scatter(table, scatter_path)
    write_report(table, report_path, histogram_path, scatter_path)
    return {"table": table_path, "histogram": histogram_path, "scatter": scatter_path, "report": report_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create bio-energy detection report artifacts.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy")
    parser.add_argument("--seq-len", type=int, default=24)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = create_report(args.artifact_dir, seq_len=args.seq_len)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
