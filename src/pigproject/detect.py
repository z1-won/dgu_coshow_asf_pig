"""Calibrate reconstruction threshold and detect anomalous windows."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from tensorflow import keras


def reconstruction_error(model: keras.Model, X: np.ndarray) -> np.ndarray:
    X_pred = model.predict(X, verbose=0)
    return np.mean(np.square(X - X_pred), axis=(1, 2))


def calibrate_threshold(model: keras.Model, X_val: np.ndarray, percentile: float = 99.0) -> float:
    errors = reconstruction_error(model, X_val)
    return float(np.percentile(errors, percentile))


def confirm_consecutive(raw_flags: np.ndarray, consecutive_required: int = 3) -> np.ndarray:
    confirmed = np.zeros_like(raw_flags, dtype=bool)
    count = 0
    for idx, flag in enumerate(raw_flags):
        count = count + 1 if flag else 0
        if count >= consecutive_required:
            confirmed[idx - consecutive_required + 1 : idx + 1] = True
    return confirmed


def detect_anomalies(
    model: keras.Model,
    X_new: np.ndarray,
    threshold: float,
    consecutive_required: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    errors = reconstruction_error(model, X_new)
    raw_flags = errors > threshold
    confirmed = confirm_consecutive(raw_flags, consecutive_required=consecutive_required)
    return errors, raw_flags, confirmed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect anomalies with a trained LSTM Autoencoder.")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--model-name", default="best_model.keras")
    parser.add_argument("--input", default=None, help="Optional .npy sequence array. Defaults to X_val.npy.")
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = Path(args.artifact_dir)
    model = keras.models.load_model(artifacts / args.model_name)
    X_val = np.load(artifacts / "X_val.npy")

    threshold = calibrate_threshold(model, X_val, percentile=args.percentile)
    np.save(artifacts / "threshold.npy", threshold)

    X_new = np.load(args.input) if args.input else X_val
    errors, raw_flags, confirmed_flags = detect_anomalies(
        model,
        X_new,
        threshold,
        consecutive_required=args.consecutive_required,
    )

    np.save(artifacts / "last_errors.npy", errors)
    np.save(artifacts / "last_raw_flags.npy", raw_flags)
    np.save(artifacts / "last_confirmed_flags.npy", confirmed_flags)
    print(f"threshold: {threshold:.6f}")
    print("raw anomaly windows:", int(raw_flags.sum()))
    print("confirmed anomaly windows:", int(confirmed_flags.sum()))


if __name__ == "__main__":
    main()
