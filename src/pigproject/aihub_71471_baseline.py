"""Train and evaluate a 71471-only behavior anomaly baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from tensorflow import keras

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.aihub_71471_timeseries import model_feature_columns
from pigproject.detect import bootstrap_percentile_ci, detect_anomalies, reconstruction_error
from pigproject.model import build_lstm_autoencoder


GROUP_COLUMNS = ["farm_id", "channel"]


def load_71471_timeseries(input_path: str | Path, feature_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(input_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values(["farm_id", "channel", "datetime"]).reset_index(drop=True)
    selected = feature_columns or model_feature_columns()
    selected = [col for col in selected if col in df.columns]
    if not selected:
        raise ValueError("No usable 71471 behavior feature columns found.")
    df[selected] = df[selected].apply(pd.to_numeric, errors="coerce").fillna(0)
    return df, selected


def fit_global_normal_scaler(train_normal: pd.DataFrame, feature_columns: list[str]) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(train_normal[feature_columns])
    return scaler


def transform_global_scaler(
    df: pd.DataFrame,
    feature_columns: list[str],
    scaler: StandardScaler,
) -> pd.DataFrame:
    scaled = df.copy()
    scaled[feature_columns] = scaled[feature_columns].astype(float)
    scaled[feature_columns] = scaler.transform(scaled[feature_columns])
    return scaled


def create_labeled_sequences(
    df: pd.DataFrame,
    feature_columns: list[str],
    seq_len: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    sequences = []
    metadata_rows = []
    for group_key, group in df.groupby(GROUP_COLUMNS, dropna=False):
        farm_id, channel = group_key
        group = group.sort_values("datetime").reset_index(drop=True)
        values = group[feature_columns].to_numpy(dtype=np.float32)
        for start in range(len(values) - seq_len + 1):
            end = start + seq_len
            window = group.iloc[start:end]
            sequences.append(values[start:end])
            metadata_rows.append(
                {
                    "farm_id": farm_id,
                    "channel": channel,
                    "split": window["split"].mode().iloc[0],
                    "start_datetime": window["datetime"].iloc[0],
                    "end_datetime": window["datetime"].iloc[-1],
                    "estrus_ratio_mean": float(window["estrus_ratio"].mean()),
                    "estrus_ratio_max": float(window["estrus_ratio"].max()),
                    "injected_ratio_mean": float(window["injected_ratio"].mean()),
                    "row_count": len(window),
                }
            )
    return np.asarray(sequences, dtype=np.float32), pd.DataFrame(metadata_rows)


def split_sequence_sets(
    sequences: np.ndarray,
    metadata: pd.DataFrame,
) -> dict[str, tuple[np.ndarray, pd.DataFrame]]:
    train_mask = (metadata["split"] == "training") & (metadata["estrus_ratio_max"] == 0)
    val_normal_mask = (metadata["split"] == "validation") & (metadata["estrus_ratio_max"] == 0)
    val_estrus_mask = (metadata["split"] == "validation") & (metadata["estrus_ratio_max"] > 0)
    return {
        "train_normal": (sequences[train_mask.to_numpy()], metadata[train_mask].reset_index(drop=True)),
        "val_normal": (sequences[val_normal_mask.to_numpy()], metadata[val_normal_mask].reset_index(drop=True)),
        "val_estrus": (sequences[val_estrus_mask.to_numpy()], metadata[val_estrus_mask].reset_index(drop=True)),
    }


def build_71471_baseline_dataset(
    input_path: str | Path,
    output_dir: str | Path,
    seq_len: int = 24,
    feature_columns: list[str] | None = None,
) -> dict[str, tuple[np.ndarray, pd.DataFrame]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df, selected = load_71471_timeseries(input_path, feature_columns=feature_columns)
    train_normal = df[(df["split"] == "training") & (df["estrus_ratio"] == 0)].copy()
    if train_normal.empty:
        raise ValueError("No ESTRUS=0 training rows found for 71471 normal baseline.")

    scaler = fit_global_normal_scaler(train_normal, selected)
    scaled = transform_global_scaler(df, selected, scaler)
    sequences, metadata = create_labeled_sequences(scaled, selected, seq_len=seq_len)
    sets = split_sequence_sets(sequences, metadata)

    for name, (X, meta) in sets.items():
        np.save(output / f"X_{name}.npy", X)
        meta.to_csv(output / f"{name}_sequence_metadata.csv", index=False)

    scaled.to_csv(output / "aihub_71471_scaled_timeseries.csv", index=False)
    metadata.to_csv(output / "aihub_71471_all_sequence_metadata.csv", index=False)
    (output / "aihub_71471_feature_columns.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    joblib.dump(
        {
            "scaler": scaler,
            "feature_columns": selected,
            "scaling_mode": "global_training_estrus_negative",
        },
        output / "aihub_71471_scaler.joblib",
    )
    return sets


def train_baseline(
    output_dir: str | Path,
    latent_dim: int = 24,
    epochs: int = 30,
    batch_size: int = 32,
) -> keras.Model:
    output = Path(output_dir)
    X_train = np.load(output / "X_train_normal.npy")
    X_val = np.load(output / "X_val_normal.npy")
    if len(X_train) == 0 or len(X_val) == 0:
        raise ValueError("71471 baseline needs non-empty train_normal and val_normal sequence sets.")
    model = build_lstm_autoencoder(seq_len=X_train.shape[1], n_features=X_train.shape[2], latent_dim=latent_dim)
    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=6, restore_best_weights=True),
        keras.callbacks.ModelCheckpoint(output / "best_model.keras", monitor="val_loss", save_best_only=True),
    ]
    model.fit(
        X_train,
        X_train,
        validation_data=(X_val, X_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        shuffle=True,
        verbose=1,
    )
    model.save(output / "final_model.keras")
    return model


def _group_ids(metadata: pd.DataFrame) -> np.ndarray:
    return (metadata["farm_id"].astype(str) + "_" + metadata["channel"].astype(str)).to_numpy()


def evaluate_baseline(
    output_dir: str | Path,
    percentile: float = 99.0,
    consecutive_required: int = 3,
) -> pd.DataFrame:
    output = Path(output_dir)
    model = keras.models.load_model(output / "best_model.keras")
    X_val = np.load(output / "X_val_normal.npy")
    val_meta = pd.read_csv(output / "val_normal_sequence_metadata.csv")
    val_errors = reconstruction_error(model, X_val)
    threshold = float(np.percentile(val_errors, percentile))
    ci = bootstrap_percentile_ci(val_errors, percentile=percentile)
    np.save(output / "threshold.npy", threshold)
    pd.DataFrame([ci]).to_csv(output / "threshold_confidence.csv", index=False)

    rows = []
    scored_frames = []
    for split_name in ["val_normal", "val_estrus"]:
        X = np.load(output / f"X_{split_name}.npy")
        meta = pd.read_csv(output / f"{split_name}_sequence_metadata.csv")
        group_ids = _group_ids(meta) if len(meta) == len(X) else None
        errors, raw_flags, confirmed = detect_anomalies(
            model,
            X,
            threshold=threshold,
            consecutive_required=consecutive_required,
            group_ids=group_ids,
        )
        scored = meta.copy()
        scored["reconstruction_error"] = errors
        scored["raw_anomaly"] = raw_flags
        scored["confirmed_anomaly"] = confirmed
        scored["evaluation_split"] = split_name
        scored_frames.append(scored)
        rows.append(
            {
                "evaluation_split": split_name,
                "windows": len(X),
                "mean_error": float(errors.mean()) if len(errors) else np.nan,
                "raw_anomaly_windows": int(raw_flags.sum()),
                "raw_anomaly_rate": float(raw_flags.mean()) if len(raw_flags) else np.nan,
                "confirmed_anomaly_windows": int(confirmed.sum()),
                "confirmed_anomaly_rate": float(confirmed.mean()) if len(confirmed) else np.nan,
                "threshold_p99": threshold,
                "threshold_ci_relative_width": ci["ci_relative_width"],
            }
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(output / "aihub_71471_baseline_detection_summary.csv", index=False)
    pd.concat(scored_frames, ignore_index=True).to_csv(output / "aihub_71471_scored_windows.csv", index=False)
    return summary


def write_report(output_dir: str | Path, detection_summary: pd.DataFrame) -> Path:
    output = Path(output_dir)
    train_meta = pd.read_csv(output / "train_normal_sequence_metadata.csv")
    val_normal_meta = pd.read_csv(output / "val_normal_sequence_metadata.csv")
    val_estrus_meta = pd.read_csv(output / "val_estrus_sequence_metadata.csv")
    features = json.loads((output / "aihub_71471_feature_columns.json").read_text(encoding="utf-8"))
    normal_rate = float(
        detection_summary.loc[
            detection_summary["evaluation_split"] == "val_normal",
            "confirmed_anomaly_rate",
        ].iloc[0]
    )
    estrus_rate = float(
        detection_summary.loc[
            detection_summary["evaluation_split"] == "val_estrus",
            "confirmed_anomaly_rate",
        ].iloc[0]
    )
    if normal_rate == 0 and estrus_rate == 0:
        ratio_text = "not estimable; both rates are 0.0%"
    elif normal_rate == 0:
        ratio_text = "not estimable; normal validation rate is 0.0%"
    else:
        ratio_text = f"{estrus_rate / normal_rate:.2f}x"
    report_path = output / "aihub_71471_baseline_report.md"
    lines = [
        "# AI Hub 71471 전용 행동 baseline",
        "",
        "## 목적",
        "",
        "`ESTRUS`/`INJECTION` 라벨을 입력 feature에서 제외하고, 행동/위치 feature만으로 정상 행동 baseline을 학습했습니다.",
        "",
        "## 데이터셋",
        "",
        f"- train normal sequences: `{len(train_meta)}`",
        f"- validation normal sequences: `{len(val_normal_meta)}`",
        f"- validation estrus sequences: `{len(val_estrus_meta)}`",
        f"- feature count: `{len(features)}`",
        "- scaling mode: `global_training_estrus_negative`",
        "",
        "## 사용 feature",
        "",
        ", ".join(f"`{feature}`" for feature in features),
        "",
        "## 탐지 결과",
        "",
        dataframe_to_markdown(detection_summary),
        "",
        f"- ESTRUS validation confirmed anomaly rate / normal validation rate: `{ratio_text}`",
        "",
        "## 해석",
        "",
        "- 이 결과는 ASF 탐지 성능이 아니라 행동 feature pipeline의 민감도 검증입니다.",
        "- `ESTRUS`는 평가 라벨로만 사용했기 때문에 입력 라벨 누수는 없습니다.",
        "- 현재 71471 라벨은 channel 1-8이 `ESTRUS=Y`, channel 9-16이 `ESTRUS=N`으로 분리되어 있어 발정 효과와 channel/camera 효과가 섞일 수 있습니다.",
        "- 71471과 622는 같은 농장/돈방 데이터가 아니므로, 지금 단계에서는 메인 모델에 직접 섞지 않고 보조 baseline으로 유지합니다.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train/evaluate AI Hub 71471 behavior anomaly baseline.")
    parser.add_argument("--input", default="data/processed/aihub_71471_behavior_timeseries_10min.csv")
    parser.add_argument("--output-dir", default="artifacts/aihub_71471_behavior_baseline")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--latent-dim", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=3)
    parser.add_argument("--skip-train", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_71471_baseline_dataset(args.input, args.output_dir, seq_len=args.seq_len)
    if args.skip_train:
        print(f"Built 71471 baseline dataset at {args.output_dir}")
        return
    train_baseline(args.output_dir, latent_dim=args.latent_dim, epochs=args.epochs, batch_size=args.batch_size)
    detection_summary = evaluate_baseline(
        args.output_dir,
        percentile=args.percentile,
        consecutive_required=args.consecutive_required,
    )
    report_path = write_report(args.output_dir, detection_summary)
    print(f"report: {report_path}")
    print(dataframe_to_markdown(detection_summary))


if __name__ == "__main__":
    main()
