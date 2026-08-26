"""Create model-ready arrays from resampled activity time series."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


ID_COLUMNS = ["split", "facility_number", "chamber_number", "pen_number", "datetime"]
DEFAULT_FEATURE_COLUMNS = [
    "frame_count",
    "point_annotation_count",
    "total_keypoints",
    "active_behavior_count",
    "rest_behavior_count",
    "active_behavior_ratio",
    "rest_behavior_ratio",
    "center_movement",
    "center_movement_norm",
    "mean_center_x",
    "mean_center_y",
    "std_center_x",
    "std_center_y",
    "mean_span_x",
    "mean_span_y",
    "max_span_x",
    "max_span_y",
    "lying_count",
    "lying_ratio",
    "standing_count",
    "standing_ratio",
    "walking_count",
    "walking_ratio",
    "running_count",
    "running_ratio",
    "suckling_count",
    "suckling_ratio",
    "searching_count",
    "searching_ratio",
]


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    table = df.reset_index()
    table.columns = [str(col) for col in table.columns]
    rows = ["| " + " | ".join(table.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(table.columns)) + " |")
    for _, row in table.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def load_timeseries(input_path: str | Path, feature_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(input_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])

    selected = feature_columns or DEFAULT_FEATURE_COLUMNS
    selected = [col for col in selected if col in df.columns]
    if not selected:
        raise ValueError("No feature columns are available in the input time series.")

    df[selected] = df[selected].apply(pd.to_numeric, errors="coerce")
    df[selected] = df.groupby(["facility_number", "pen_number"], dropna=False)[selected].transform(
        lambda group: group.interpolate(limit_direction="both")
    )
    df[selected] = df[selected].fillna(0)
    return df.sort_values(["split", "facility_number", "pen_number", "datetime"]), selected


def split_train_val(df: pd.DataFrame, train_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "split" in df.columns and {"training", "validation"}.issubset(set(df["split"].dropna().unique())):
        return df[df["split"] == "training"].copy(), df[df["split"] == "validation"].copy()

    train_parts = []
    val_parts = []
    for _, group in df.groupby(["facility_number", "pen_number"], dropna=False):
        group = group.sort_values("datetime")
        split_idx = int(len(group) * train_ratio)
        train_parts.append(group.iloc[:split_idx])
        val_parts.append(group.iloc[split_idx:])
    return pd.concat(train_parts), pd.concat(val_parts)


def fit_transform(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_columns: list[str],
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scaler = StandardScaler()
    scaler.fit(train_df[feature_columns])
    joblib.dump(scaler, output_dir / "activity_scaler.joblib")

    train_scaled = train_df.copy()
    val_scaled = val_df.copy()
    train_scaled[feature_columns] = scaler.transform(train_scaled[feature_columns])
    val_scaled[feature_columns] = scaler.transform(val_scaled[feature_columns])
    return train_scaled, val_scaled


def create_sequences(
    df: pd.DataFrame,
    feature_columns: list[str],
    seq_len: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    sequences = []
    metadata_rows = []
    group_cols = ["facility_number", "pen_number"]

    for (facility, pen), group in df.groupby(group_cols, dropna=False):
        group = group.sort_values("datetime").reset_index(drop=True)
        values = group[feature_columns].to_numpy(dtype=np.float32)
        for start in range(len(values) - seq_len + 1):
            end = start + seq_len - 1
            sequences.append(values[start : start + seq_len])
            metadata_rows.append(
                {
                    "facility_number": facility,
                    "pen_number": pen,
                    "start_datetime": group.loc[start, "datetime"],
                    "end_datetime": group.loc[end, "datetime"],
                    "start_row": int(start),
                    "end_row": int(end),
                }
            )

    return np.asarray(sequences, dtype=np.float32), pd.DataFrame(metadata_rows)


def write_report(
    output_dir: Path,
    feature_columns: list[str],
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    X_train: np.ndarray,
    X_val: np.ndarray,
    seq_len: int,
) -> Path:
    report = output_dir / "activity_model_dataset_report.md"
    lines = [
        "# 활동량 모델 입력 데이터셋 보고서",
        "",
        f"- 시퀀스 길이: `{seq_len}`",
        f"- feature 수: `{len(feature_columns)}`",
        f"- train row 수: `{len(train_df)}`",
        f"- val row 수: `{len(val_df)}`",
        f"- X_train shape: `{tuple(X_train.shape)}`",
        f"- X_val shape: `{tuple(X_val.shape)}`",
        "",
        "## 사용 feature",
        "",
        ", ".join(f"`{col}`" for col in feature_columns),
        "",
        "## train 돈방/pen별 row 수",
        "",
        dataframe_to_markdown(train_df.groupby(["facility_number", "pen_number"]).size().to_frame("row_count")),
        "",
        "## val 돈방/pen별 row 수",
        "",
        dataframe_to_markdown(val_df.groupby(["facility_number", "pen_number"]).size().to_frame("row_count")),
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_activity_model_dataset(
    input_path: str | Path,
    output_dir: str | Path,
    seq_len: int = 24,
    train_ratio: float = 0.8,
    feature_columns: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    df, selected_features = load_timeseries(input_path, feature_columns=feature_columns)
    train_df, val_df = split_train_val(df, train_ratio=train_ratio)
    train_scaled, val_scaled = fit_transform(train_df, val_df, selected_features, output)

    X_train, train_meta = create_sequences(train_scaled, selected_features, seq_len=seq_len)
    X_val, val_meta = create_sequences(val_scaled, selected_features, seq_len=seq_len)

    train_scaled.to_csv(output / "activity_train_scaled.csv", index=False)
    val_scaled.to_csv(output / "activity_val_scaled.csv", index=False)
    train_meta.to_csv(output / "activity_train_sequence_metadata.csv", index=False)
    val_meta.to_csv(output / "activity_val_sequence_metadata.csv", index=False)
    np.save(output / "X_train.npy", X_train)
    np.save(output / "X_val.npy", X_val)
    (output / "activity_feature_columns.json").write_text(
        json.dumps(selected_features, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(output, selected_features, train_df, val_df, X_train, X_val, seq_len=seq_len)
    return X_train, X_val


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LSTM-ready arrays from activity time series.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="artifacts/activity_model")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--features", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X_train, X_val = build_activity_model_dataset(
        input_path=args.input,
        output_dir=args.output_dir,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
        feature_columns=args.features,
    )
    print("X_train shape:", X_train.shape)
    print("X_val shape:", X_val.shape)


if __name__ == "__main__":
    main()
