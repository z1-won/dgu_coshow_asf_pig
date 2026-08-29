"""Create model-ready arrays from resampled activity time series."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from pigproject.bioenergy_pipeline import split_by_group_time

# Below this many training windows, a pen's LSTM reconstruction error isn't a
# trustworthy "normal" baseline -- it's an artifact of the model barely
# having seen that pen. 10 mirrors bioenergy_pipeline's own min_val_windows
# default, i.e. the project's existing bar for "enough windows to calibrate
# a threshold". facility3-pen7 (7 train windows out of 622's 9 pens, vs
# 86-133 for every other non-overlap pen) is the only pen this catches today
# -- see docs/ACTIVITY_PREPROCESSING_AUDIT.md.
LOW_TRAIN_WINDOWS_THRESHOLD = 10

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


def load_timeseries(
    input_path: str | Path, feature_columns: list[str] | None = None
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    df = pd.read_csv(input_path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])

    selected = feature_columns or DEFAULT_FEATURE_COLUMNS
    selected = [col for col in selected if col in df.columns]
    if not selected:
        raise ValueError("No feature columns are available in the input time series.")

    df[selected] = df[selected].apply(pd.to_numeric, errors="coerce")
    missing_before = df[selected].isna()

    df[selected] = df.groupby(["facility_number", "pen_number"], dropna=False)[selected].transform(
        lambda group: group.interpolate(limit_direction="both")
    )
    # Interpolation can't fill a pen whose entire history is missing a
    # column, so anything still NaN here gets zero-filled next. That used to
    # happen silently; report it instead, mirroring domain_rules.
    # filter_implausible_values's "report what you drop" convention on the
    # bioenergy track -- see docs/ACTIVITY_PREPROCESSING_AUDIT.md.
    still_missing = df[selected].isna()
    df[selected] = df[selected].fillna(0)

    quality_summary = pd.DataFrame(
        {
            "feature": selected,
            "missing_or_non_numeric": missing_before[selected].sum().to_numpy(),
            "filled_by_interpolation": (
                missing_before[selected].sum() - still_missing[selected].sum()
            ).to_numpy(),
            "zero_filled": still_missing[selected].sum().to_numpy(),
        }
    )

    # split_by_group_time (bioenergy_pipeline.py) computes overlap_rows from
    # each group's index min/max, which only means "row count" when each
    # (facility, pen) group's rows are index-contiguous. Sorting by "split"
    # first (as this used to) scatters each pen's rows into two far-apart
    # blocks (all pens' training rows, then all pens' validation rows) and
    # makes that arithmetic meaningless -- and split_train_val no longer
    # reads the "split" column anyway (see its docstring), so group by
    # (facility, pen) first instead, matching aggregate_by_time()'s contract
    # for the bioenergy track.
    sorted_df = df.sort_values(["facility_number", "pen_number", "datetime"]).reset_index(drop=True)
    return sorted_df, selected, quality_summary


def split_train_val(
    df: pd.DataFrame,
    train_ratio: float,
    seq_len: int = 24,
    min_val_windows: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological per-pen split guaranteeing at least min_val_windows validation windows.

    This used to prefer the AI Hub-provided "split" column when present, but
    that official split leaves 3 of the 622 dataset's 9 (facility, pen)
    groups (3/7, 3/8, 5/3) with only 4-9 validation rows -- fewer than one
    seq_len=24 window, so those pens' own "normal" pattern was never checked
    against the model's threshold and silently dropped out of every
    downstream report. Delegating to bioenergy_pipeline.split_by_group_time
    (already validated on the bioenergy track) fixes that per-group, at the
    cost of no longer matching AI Hub's original row assignment exactly; the
    default min_val_windows=3 (vs bioenergy's 10) reflects how much shorter
    these pens' full histories are -- see activity_split_summary.csv for
    which groups needed a train/val overlap to reach even that.
    """
    return split_by_group_time(
        df,
        train_ratio=train_ratio,
        seq_len=seq_len,
        min_val_windows=min_val_windows,
        group_cols=("facility_number", "pen_number"),
    )


def fit_scalers_per_pen(
    train_df: pd.DataFrame, feature_columns: list[str]
) -> dict[tuple, StandardScaler]:
    """Fit one StandardScaler per (facility_number, pen_number) group.

    Mirrors bioenergy_pipeline.fit_scalers_per_chamber for the same reason:
    facility3-pen8's active_behavior_ratio averages 0.615 while every other
    pen in the 622 dataset averages 0.05-0.12 (measured on the current
    aihub_622_activity_timeseries_10min.csv), a baseline gap wide enough that
    a single pooled scaler would let it dominate the reconstruction error
    instead of real within-pen deviations -- the same failure mode found and
    fixed on the bioenergy track in commit b6c3ec6.
    """
    scalers: dict[tuple, StandardScaler] = {}
    for (facility, pen), group in train_df.groupby(["facility_number", "pen_number"], dropna=False):
        scaler = StandardScaler()
        scaler.fit(group[feature_columns])
        scalers[(facility, pen)] = scaler
    return scalers


def transform_per_pen(
    df: pd.DataFrame, feature_columns: list[str], scalers: dict[tuple, StandardScaler]
) -> pd.DataFrame:
    scaled = df.copy()
    scaled[feature_columns] = scaled[feature_columns].astype(float)
    for (facility, pen), group in df.groupby(["facility_number", "pen_number"], dropna=False):
        key = (facility, pen)
        if key not in scalers:
            raise KeyError(f"No scaler fitted for pen group {key}; it must appear in the training split.")
        scaled.loc[group.index, feature_columns] = scalers[key].transform(group[feature_columns])
    return scaled


def fit_transform(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_columns: list[str],
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scalers = fit_scalers_per_pen(train_df, feature_columns)
    joblib.dump(
        {"scalers": scalers, "feature_columns": feature_columns, "scaling_mode": "per_pen"},
        output_dir / "activity_scaler.joblib",
    )

    train_scaled = transform_per_pen(train_df, feature_columns, scalers)
    val_scaled = transform_per_pen(val_df, feature_columns, scalers)
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
    split_summary: pd.DataFrame,
    quality_summary: pd.DataFrame,
) -> Path:
    report = output_dir / "activity_model_dataset_report.md"
    skipped = split_summary[split_summary["status"] != "non_overlapping"]
    low_confidence = split_summary[split_summary["low_confidence"]]
    missing_features = quality_summary[quality_summary["missing_or_non_numeric"] > 0]
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
        "## 결측치/비수치 처리 (`activity_data_quality_report.csv`)",
        "",
        "결측/비수치 값은 같은 (facility, pen) 안에서 시간순 보간(interpolate)을 먼저 시도하고, "
        "그래도 남으면(예: 한 pen의 전체 기간에 그 feature 값이 아예 없는 경우) 0으로 채웁니다. "
        f"현재 입력 데이터에는 {'결측/비수치 값이 없습니다.' if not len(missing_features) else '아래 feature에 결측/비수치 값이 있습니다.'}",
        "",
    ]
    if len(missing_features):
        lines += [dataframe_to_markdown(missing_features), ""]
    lines += [
        "## train 돈방/pen별 row 수",
        "",
        dataframe_to_markdown(train_df.groupby(["facility_number", "pen_number"]).size().to_frame("row_count")),
        "",
        "## val 돈방/pen별 row 수",
        "",
        dataframe_to_markdown(val_df.groupby(["facility_number", "pen_number"]).size().to_frame("row_count")),
        "",
        "## Pen별 split 상세 (`activity_split_summary.csv`)",
        "",
        "`status`가 `non_overlapping`이 아닌 pen은 min_val_windows를 채우기 위해 train/val이 겹치거나(`overlap_for_short_group`), "
        "데이터가 너무 짧아 아예 제외됐다(`skipped_too_short`/`skipped_no_windows`).",
        "",
        dataframe_to_markdown(split_summary),
    ]
    if len(skipped):
        lines += [
            "",
            "### 정상 분리가 안 된 pen",
            "",
            dataframe_to_markdown(skipped),
        ]
    if len(low_confidence):
        lines += [
            "",
            f"### 참고용(데이터 부족) pen — train window {LOW_TRAIN_WINDOWS_THRESHOLD}개 미만",
            "",
            "이 pen들은 학습 시퀀스가 너무 적어 reconstruction error가 그 pen의 진짜 '정상' 기준을 "
            "반영한다고 보기 어렵습니다. 탐지 결과에는 포함되지만 경보/랭킹에서는 참고용으로만 다뤄야 합니다.",
            "",
            dataframe_to_markdown(low_confidence),
        ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_activity_model_dataset(
    input_path: str | Path,
    output_dir: str | Path,
    seq_len: int = 24,
    train_ratio: float = 0.8,
    min_val_windows: int = 3,
    feature_columns: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    df, selected_features, quality_summary = load_timeseries(input_path, feature_columns=feature_columns)
    quality_summary.to_csv(output / "activity_data_quality_report.csv", index=False)
    train_df, val_df, split_summary = split_train_val(
        df, train_ratio=train_ratio, seq_len=seq_len, min_val_windows=min_val_windows
    )
    split_summary["low_confidence"] = split_summary["train_windows"] < LOW_TRAIN_WINDOWS_THRESHOLD
    split_summary.to_csv(output / "activity_split_summary.csv", index=False)
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
    write_report(
        output,
        selected_features,
        train_df,
        val_df,
        X_train,
        X_val,
        seq_len=seq_len,
        split_summary=split_summary,
        quality_summary=quality_summary,
    )
    return X_train, X_val


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build LSTM-ready arrays from activity time series.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="artifacts/activity_model")
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--min-val-windows", type=int, default=3)
    parser.add_argument("--features", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X_train, X_val = build_activity_model_dataset(
        input_path=args.input,
        output_dir=args.output_dir,
        seq_len=args.seq_len,
        train_ratio=args.train_ratio,
        min_val_windows=args.min_val_windows,
        feature_columns=args.features,
    )
    print("X_train shape:", X_train.shape)
    print("X_val shape:", X_val.shape)


if __name__ == "__main__":
    main()
