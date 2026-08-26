"""Compare anomaly thresholds across percentiles."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow import keras

from pigproject.detect import confirm_consecutive, load_group_ids, reconstruction_error


def compare_thresholds(
    artifact_dir: str | Path,
    percentiles: list[float],
    consecutive_required: int = 3,
    seq_len: int = 24,
) -> pd.DataFrame:
    artifacts = Path(artifact_dir)
    model = keras.models.load_model(artifacts / "best_model.keras")
    X_val = np.load(artifacts / "X_val.npy")
    errors = reconstruction_error(model, X_val)
    group_ids = load_group_ids(artifacts, seq_len=seq_len)
    if group_ids is not None and len(group_ids) != len(X_val):
        group_ids = None

    rows = []
    for percentile in percentiles:
        threshold = float(np.percentile(errors, percentile))
        raw_flags = errors > threshold
        confirmed_flags = confirm_consecutive(raw_flags, consecutive_required=consecutive_required, group_ids=group_ids)
        rows.append(
            {
                "percentile": percentile,
                "threshold": threshold,
                "raw_anomaly_windows": int(raw_flags.sum()),
                "confirmed_anomaly_windows": int(confirmed_flags.sum()),
                "error_min": float(errors.min()),
                "error_median": float(np.median(errors)),
                "error_mean": float(errors.mean()),
                "error_max": float(errors.max()),
            }
        )

    np.save(artifacts / "threshold_compare_errors.npy", errors)
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare percentile thresholds for validation errors.")
    parser.add_argument("--artifact-dir", default="artifacts/bioenergy")
    parser.add_argument("--percentiles", nargs="+", type=float, default=[95.0, 97.0, 99.0])
    parser.add_argument("--consecutive-required", type=int, default=3)
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output) if args.output else Path(args.artifact_dir) / "bioenergy_threshold_comparison.csv"
    df = compare_thresholds(
        artifact_dir=args.artifact_dir,
        percentiles=args.percentiles,
        consecutive_required=args.consecutive_required,
        seq_len=args.seq_len,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"threshold_comparison: {output}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
