"""Explain clean baseline anomaly scores with feature errors and PCA views."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sklearn.decomposition import PCA
from tensorflow import keras

from pigproject.bioenergy_baseline_overview import build_split_table
from pigproject.bioenergy_report import dataframe_to_markdown, load_window_metadata
from pigproject.detect import confirm_consecutive


def load_feature_columns(artifact_dir: str | Path) -> list[str]:
    path = Path(artifact_dir) / "bioenergy_feature_columns.csv"
    return pd.read_csv(path)["feature"].tolist()


def build_feature_error_table(
    artifact_dir: str | Path,
    seq_len: int = 24,
    model_name: str = "best_model.keras",
) -> pd.DataFrame:
    artifacts = Path(artifact_dir)
    model = keras.models.load_model(artifacts / model_name)
    threshold = float(np.load(artifacts / "threshold.npy"))
    feature_columns = load_feature_columns(artifacts)

    frames = []
    for split in ["train", "val"]:
        X = np.load(artifacts / f"X_{split}.npy")
        pred = model.predict(X, verbose=0)
        per_feature_error = np.mean(np.square(X - pred), axis=1)
        total_error = per_feature_error.mean(axis=1)
        raw_flags = total_error > threshold
        confirmed_flags = confirm_consecutive(raw_flags, consecutive_required=3)
        metadata = load_window_metadata(artifacts / f"bioenergy_{split}_scaled.csv", seq_len=seq_len)
        rows = []
        for idx in range(len(X)):
            feature_errors = per_feature_error[idx]
            top_indices = np.argsort(feature_errors)[::-1][:5]
            row = metadata.iloc[idx].to_dict()
            row.update(
                {
                    "split": split,
                    "reconstruction_error": total_error[idx],
                    "threshold": threshold,
                    "raw_anomaly": bool(raw_flags[idx]),
                    "confirmed_anomaly": bool(confirmed_flags[idx]),
                    "top_feature_1": feature_columns[top_indices[0]],
                    "top_feature_1_error": feature_errors[top_indices[0]],
                    "top_feature_2": feature_columns[top_indices[1]],
                    "top_feature_2_error": feature_errors[top_indices[1]],
                    "top_feature_3": feature_columns[top_indices[2]],
                    "top_feature_3_error": feature_errors[top_indices[2]],
                    "top_feature_4": feature_columns[top_indices[3]],
                    "top_feature_4_error": feature_errors[top_indices[3]],
                    "top_feature_5": feature_columns[top_indices[4]],
                    "top_feature_5_error": feature_errors[top_indices[4]],
                }
            )
            for feature, value in zip(feature_columns, feature_errors):
                row[f"error_{feature}"] = value
            rows.append(row)
        frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True)


def build_pca_table(
    artifact_dir: str | Path,
    seq_len: int = 24,
    model_name: str = "best_model.keras",
) -> pd.DataFrame:
    artifacts = Path(artifact_dir)
    split_table = build_split_table(artifacts, seq_len=seq_len, model_name=model_name)
    X_train = np.load(artifacts / "X_train.npy")
    X_val = np.load(artifacts / "X_val.npy")
    X_all = np.concatenate([X_train, X_val], axis=0)
    flat = X_all.reshape((X_all.shape[0], -1))
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(flat)
    out = split_table.copy()
    out["pc1"] = coords[:, 0]
    out["pc2"] = coords[:, 1]
    out["pca_explained_variance_ratio_pc1"] = pca.explained_variance_ratio_[0]
    out["pca_explained_variance_ratio_pc2"] = pca.explained_variance_ratio_[1]
    return out


def _scale(value: float, min_value: float, max_value: float, size: int) -> float:
    if min_value == max_value:
        return size / 2
    return ((value - min_value) / (max_value - min_value)) * size


def draw_pca_scatter(table: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1500, 1000
    margin_l, margin_r, margin_t, margin_b = 105, 70, 85, 130
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    min_x, max_x = float(table["pc1"].min()), float(table["pc1"].max())
    min_y, max_y = float(table["pc2"].min()), float(table["pc2"].max())
    pad_x = max((max_x - min_x) * 0.08, 0.1)
    pad_y = max((max_y - min_y) * 0.08, 0.1)
    min_x, max_x = min_x - pad_x, max_x + pad_x
    min_y, max_y = min_y - pad_y, max_y + pad_y

    train_count = int((table["split"] == "train").sum())
    val_count = int((table["split"] == "val").sum())
    var1 = float(table["pca_explained_variance_ratio_pc1"].iloc[0]) * 100
    var2 = float(table["pca_explained_variance_ratio_pc2"].iloc[0]) * 100
    draw.text((margin_l, 30), "Clean Baseline PCA Cluster Scatter", fill="#222222", font=font)
    draw.text((margin_l, 53), f"train={train_count}, validation={val_count}, PC1={var1:.1f}%, PC2={var2:.1f}%", fill="#555555", font=font)
    draw.text((margin_l, 73), "PC1/PC2 are compressed combinations of all selected features over 24 timesteps.", fill="#555555", font=font)

    draw.rectangle((margin_l, margin_t, margin_l + plot_w, margin_t + plot_h), outline="#333333", width=2)
    for frac in np.linspace(0.25, 0.75, 3):
        xx = margin_l + frac * plot_w
        yy = margin_t + frac * plot_h
        draw.line((xx, margin_t, xx, margin_t + plot_h), fill="#e6e0d8", width=1)
        draw.line((margin_l, yy, margin_l + plot_w, yy), fill="#e6e0d8", width=1)

    for _, row in table.iterrows():
        xx = margin_l + _scale(float(row["pc1"]), min_x, max_x, plot_w)
        yy = margin_t + plot_h - _scale(float(row["pc2"]), min_y, max_y, plot_h)
        if bool(row["confirmed_anomaly"]):
            fill = "#d24c34"
            radius = 7
        elif bool(row["raw_anomaly"]):
            fill = "#f0a13a"
            radius = 7
        elif row["split"] == "train":
            fill = "#2e78b7"
            radius = 5
        else:
            fill = "#2f9d68"
            radius = 6
        draw.ellipse((xx - radius, yy - radius, xx + radius, yy + radius), fill=fill, outline="#ffffff")

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
    draw.text((margin_l, height - 45), "x-axis: PC1 = largest combined variation of selected sensor patterns", fill="#555555", font=font)
    draw.text((width - 520, height - 45), "y-axis: PC2 = second-largest independent variation", fill="#555555", font=font)
    image.save(output, "JPEG", quality=92)
    return output


def draw_feature_bar(top_features: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 760
    margin_l, margin_r, margin_t, margin_b = 280, 70, 85, 70
    plot_w = width - margin_l - margin_r
    image = Image.new("RGB", (width, height), "#fbfaf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((margin_l, 30), "Top Feature Errors In Highest-Score Windows", fill="#222222", font=font)
    draw.text((margin_l, 53), "larger bar = more contribution to reconstruction error", fill="#555555", font=font)

    rows = top_features.head(12).copy()
    max_value = max(float(rows["mean_error"].max()), 1e-9)
    bar_h = 34
    gap = 13
    y = margin_t
    for _, row in rows.iterrows():
        value = float(row["mean_error"])
        bar_w = (value / max_value) * plot_w
        draw.text((30, y + 8), str(row["feature"]), fill="#333333", font=font)
        draw.rectangle((margin_l, y, margin_l + bar_w, y + bar_h), fill="#2e78b7")
        draw.text((margin_l + bar_w + 8, y + 8), f"{value:.4f}", fill="#333333", font=font)
        y += bar_h + gap
    image.save(output, "JPEG", quality=92)
    return output


def write_explain_report(
    feature_table: pd.DataFrame,
    pca_table: pd.DataFrame,
    output_path: str | Path,
    pca_scatter_path: str | Path,
    feature_bar_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    high = feature_table.sort_values("reconstruction_error", ascending=False).head(10)
    cols = [
        "split",
        "dataset_key",
        "chamber_number",
        "start_datetime",
        "end_datetime",
        "reconstruction_error",
        "top_feature_1",
        "top_feature_2",
        "top_feature_3",
        "raw_anomaly",
        "confirmed_anomaly",
    ]
    high_view = high[cols].copy()
    high_view["reconstruction_error"] = high_view["reconstruction_error"].round(6)
    error_cols = [col for col in feature_table.columns if col.startswith("error_")]
    top_features = (
        high[error_cols]
        .mean()
        .rename_axis("feature")
        .reset_index(name="mean_error")
        .sort_values("mean_error", ascending=False)
    )
    top_features["feature"] = top_features["feature"].str.removeprefix("error_")
    top_features["mean_error"] = top_features["mean_error"].round(6)
    var1 = float(pca_table["pca_explained_variance_ratio_pc1"].iloc[0]) * 100
    var2 = float(pca_table["pca_explained_variance_ratio_pc2"].iloc[0]) * 100

    lines = [
        "# 왜 기존 그래프가 답답했는지 추적",
        "",
        "## 1. 결론",
        "",
        "기존 산포도는 x축이 시간/window 순서이고 y축이 최종 anomaly score 하나라서, 어떤 요인이 다른지 보여주지 못했다.",
        "",
        "이번 분석에서는 두 가지를 추가했다.",
        "",
        "- feature error: 점수가 높은 window에서 어떤 피처의 복원 오차가 컸는지",
        "- PCA cluster scatter: SVM 예시처럼 데이터가 2차원 공간에서 어떤 군집 모양을 보이는지",
        "",
        "## 2. 새 그래프",
        "",
        f"- PCA cluster scatter: `{pca_scatter_path}`",
        f"- Feature contribution bar: `{feature_bar_path}`",
        "",
        "## 3. PCA 그래프 해석",
        "",
        f"- PC1 설명력: `{var1:.2f}%`",
        f"- PC2 설명력: `{var2:.2f}%`",
        "",
        "PCA 그래프의 x/y축은 특정 센서 하나가 아니라, 24개 피처와 24개 시점 흐름을 2차원으로 압축한 방향이다.",
        "x축 PC1은 전체 선택 피처 조합 중 데이터 차이를 가장 크게 설명하는 방향이고, y축 PC2는 PC1과 겹치지 않는 두 번째 차이 방향이다.",
        "따라서 SVM 군집 그림처럼 정상 데이터가 어디에 모여 있는지, 검증 데이터가 그 군집 안에 있는지 보는 용도에 가깝다.",
        "",
        "## 4. 점수가 높은 window의 주요 요인",
        "",
        dataframe_to_markdown(top_features.head(12)),
        "",
        "## 5. 점수가 높은 window별 상위 요인",
        "",
        dataframe_to_markdown(high_view),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def create_explanation(artifact_dir: str | Path, seq_len: int = 24, model_name: str = "best_model.keras") -> dict[str, Path]:
    artifacts = Path(artifact_dir)
    feature_table = build_feature_error_table(artifacts, seq_len=seq_len, model_name=model_name)
    pca_table = build_pca_table(artifacts, seq_len=seq_len, model_name=model_name)
    feature_table_path = artifacts / "bioenergy_feature_error_explanation.csv"
    pca_table_path = artifacts / "bioenergy_pca_windows.csv"
    pca_scatter_path = artifacts / "bioenergy_pca_cluster_scatter.jpg"
    feature_bar_path = artifacts / "bioenergy_top_feature_error_bar.jpg"
    report_path = artifacts / "bioenergy_explanation_report.md"

    feature_table.to_csv(feature_table_path, index=False)
    pca_table.to_csv(pca_table_path, index=False)
    draw_pca_scatter(pca_table, pca_scatter_path)
    high = feature_table.sort_values("reconstruction_error", ascending=False).head(10)
    error_cols = [col for col in feature_table.columns if col.startswith("error_")]
    top_features = (
        high[error_cols]
        .mean()
        .rename_axis("feature")
        .reset_index(name="mean_error")
        .sort_values("mean_error", ascending=False)
    )
    top_features["feature"] = top_features["feature"].str.removeprefix("error_")
    draw_feature_bar(top_features, feature_bar_path)
    write_explain_report(feature_table, pca_table, report_path, pca_scatter_path, feature_bar_path)
    return {
        "feature_table": feature_table_path,
        "pca_table": pca_table_path,
        "pca_scatter": pca_scatter_path,
        "feature_bar": feature_bar_path,
        "report": report_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explain bio-energy baseline anomaly scores.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy_clean_baseline")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--model-name", default="best_model.keras")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = create_explanation(args.artifact_dir, seq_len=args.seq_len, model_name=args.model_name)
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
