"""Turn generic pig-detect output into a per-window activity detection report.

pig-detect already writes last_errors.npy/last_raw_flags.npy/last_confirmed_
flags.npy for any artifact dir with X_val.npy + a trained model, activity
included. What was missing was a reproducible step joining those arrays back
onto facility_number/pen_number/start_datetime/end_datetime (previously done
by hand, which is why lstm_val_results.csv had no generating script -- see
final_ensemble.py, which reads this file). create_sequences() in
activity_model_dataset.py builds activity_val_sequence_metadata.csv in the
same per-(facility, pen) groupby order it builds X_val, so row order lines up
with last_errors.npy without needing a merge key.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown


def make_error_table(artifact_dir: str | Path) -> pd.DataFrame:
    artifacts = Path(artifact_dir)
    errors = np.load(artifacts / "last_errors.npy")
    raw_flags = np.load(artifacts / "last_raw_flags.npy")
    confirmed_flags = np.load(artifacts / "last_confirmed_flags.npy")
    threshold = float(np.load(artifacts / "threshold.npy"))
    metadata = pd.read_csv(artifacts / "activity_val_sequence_metadata.csv")

    if len(metadata) != len(errors):
        raise ValueError(f"Metadata/errors length mismatch: {len(metadata)} != {len(errors)}")

    metadata = metadata.copy()
    metadata["reconstruction_error"] = errors
    metadata["threshold"] = threshold
    metadata["raw_anomaly"] = raw_flags
    metadata["confirmed_anomaly"] = confirmed_flags

    # activity_model_dataset.build_activity_model_dataset() flags pens with
    # too few training windows (< LOW_TRAIN_WINDOWS_THRESHOLD) as
    # low_confidence in activity_split_summary.csv -- their reconstruction
    # error reflects an undertrained baseline, not a real anomaly signal, so
    # carry that flag through instead of presenting every pen as equally
    # trustworthy.
    split_summary_path = artifacts / "activity_split_summary.csv"
    if split_summary_path.exists():
        split_summary = pd.read_csv(split_summary_path)[["facility_number", "pen_number", "low_confidence"]]
        metadata = metadata.merge(split_summary, on=["facility_number", "pen_number"], how="left")
        metadata["low_confidence"] = metadata["low_confidence"].fillna(False)
    else:
        metadata["low_confidence"] = False

    return metadata.sort_values("reconstruction_error", ascending=False).reset_index(drop=True)


def write_report(table: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    threshold = float(table["threshold"].iloc[0]) if len(table) else float("nan")

    by_pen = (
        table.groupby(["facility_number", "pen_number", "low_confidence"], dropna=False)
        .agg(
            windows=("reconstruction_error", "size"),
            mean_error=("reconstruction_error", "mean"),
            max_error=("reconstruction_error", "max"),
            raw_anomalies=("raw_anomaly", "sum"),
            confirmed_anomalies=("confirmed_anomaly", "sum"),
        )
        .reset_index()
        .sort_values("max_error", ascending=False)
    )

    normal_table = table[~table["low_confidence"]]
    low_confidence_table = table[table["low_confidence"]]
    detail_cols = [
        "facility_number",
        "pen_number",
        "start_datetime",
        "end_datetime",
        "reconstruction_error",
        "raw_anomaly",
        "confirmed_anomaly",
    ]

    lines = [
        "# LSTM Autoencoder Detection Report",
        "",
        "## Run settings",
        "",
        f"- Threshold: `{threshold:.6f}`",
        f"- Validation windows: `{len(table)}` (참고용 데이터 부족 pen 제외 `{len(normal_table)}`)",
        f"- Raw anomaly windows: `{int(table['raw_anomaly'].sum())}` "
        f"(그중 참고용 pen: `{int(low_confidence_table['raw_anomaly'].sum())}`)",
        f"- Confirmed anomaly windows: `{int(table['confirmed_anomaly'].sum())}`",
        "",
        "## Top reconstruction errors (참고용 데이터 부족 pen 제외)",
        "",
        dataframe_to_markdown(normal_table.head(10)[detail_cols]) if len(normal_table) else "없음.",
    ]
    if len(low_confidence_table):
        lines += [
            "",
            "## 참고용(데이터 부족) pen의 window -- 정상 기준으로 신뢰하지 말 것",
            "",
            "이 window들의 reconstruction error가 threshold를 밀어올릴 수는 있지만, "
            "학습 시퀀스가 너무 적은 pen이라 '이상'이 아니라 '학습 부족'을 반영할 가능성이 높습니다.",
            "",
            dataframe_to_markdown(low_confidence_table[detail_cols]),
        ]
    lines += [
        "",
        "## Summary by pen",
        "",
        dataframe_to_markdown(by_pen),
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a per-window detection report/table for the activity track.")
    parser.add_argument("--artifact-dir", default="artifacts/activity_model_10min")
    parser.add_argument("--results-csv", default=None, help="Defaults to <artifact-dir>/lstm_val_results.csv")
    parser.add_argument("--report", default=None, help="Defaults to <artifact-dir>/lstm_detection_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = Path(args.artifact_dir)
    table = make_error_table(artifacts)

    results_csv = Path(args.results_csv) if args.results_csv else artifacts / "lstm_val_results.csv"
    report_path = Path(args.report) if args.report else artifacts / "lstm_detection_report.md"
    table.to_csv(results_csv, index=False)
    write_report(table, report_path)

    print(f"results: {results_csv}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
