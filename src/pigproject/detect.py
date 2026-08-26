"""Calibrate reconstruction threshold and detect anomalous windows."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow import keras


def reconstruction_error(model: keras.Model, X: np.ndarray) -> np.ndarray:
    X_pred = model.predict(X, verbose=0)
    return np.mean(np.square(X - X_pred), axis=(1, 2))


def calibrate_threshold(model: keras.Model, X_val: np.ndarray, percentile: float = 99.0) -> float:
    errors = reconstruction_error(model, X_val)
    return float(np.percentile(errors, percentile))


def bootstrap_percentile_ci(
    errors: np.ndarray,
    percentile: float,
    n_bootstrap: int = 2000,
    ci: float = 0.90,
    random_state: int = 42,
) -> dict[str, float]:
    """Bootstrap confidence interval for an empirical-percentile threshold.

    With only a few dozen validation windows, np.percentile(errors, 99) is
    close to just reading off the single highest observed error: which
    windows happen to land in the validation split can swing the threshold a
    lot, but a bare point estimate hides that. Resampling the validation
    errors with replacement and recomputing the percentile many times turns
    that hidden fragility into an explicit interval instead of a single
    falsely-confident number. Widen the interval (i.e. treat the threshold as
    unreliable) whenever ci_relative_width is large, and prefer collecting
    more validation data over trusting a narrow-looking point estimate.
    """
    errors = np.asarray(errors, dtype=float)
    n = len(errors)
    point = float(np.percentile(errors, percentile))
    if n < 2:
        return {
            "percentile": percentile,
            "threshold": point,
            "ci_lower": point,
            "ci_upper": point,
            "ci_width": 0.0,
            "ci_relative_width": 0.0,
            "n_samples": n,
            "ci_level": ci,
        }

    rng = np.random.default_rng(random_state)
    resampled = rng.choice(errors, size=(n_bootstrap, n), replace=True)
    boot_thresholds = np.percentile(resampled, percentile, axis=1)
    alpha = (1 - ci) / 2
    lower = float(np.quantile(boot_thresholds, alpha))
    upper = float(np.quantile(boot_thresholds, 1 - alpha))
    width = upper - lower
    relative_width = width / point if point else float("inf")
    return {
        "percentile": percentile,
        "threshold": point,
        "ci_lower": lower,
        "ci_upper": upper,
        "ci_width": width,
        "ci_relative_width": relative_width,
        "n_samples": n,
        "ci_level": ci,
    }


def confirm_consecutive(
    raw_flags: np.ndarray,
    consecutive_required: int = 3,
    group_ids: np.ndarray | None = None,
) -> np.ndarray:
    """Flag windows that stay above threshold for consecutive_required windows in a row.

    Sequence arrays are built by concatenating one chamber/pen's windows after
    another (see bioenergy_pipeline.create_sequences / activity_model_dataset.
    create_sequences), so a run of raw flags can span the boundary between two
    unrelated chambers. Passing group_ids (one id per window, e.g. "dataset_
    key_chamber_number") resets the run count at those boundaries so a
    confirmed anomaly always comes from one chamber's own consecutive windows.
    """
    confirmed = np.zeros_like(raw_flags, dtype=bool)
    count = 0
    for idx, flag in enumerate(raw_flags):
        if group_ids is not None and idx > 0 and group_ids[idx] != group_ids[idx - 1]:
            count = 0
        count = count + 1 if flag else 0
        if count >= consecutive_required:
            confirmed[idx - consecutive_required + 1 : idx + 1] = True
    return confirmed


def detect_anomalies(
    model: keras.Model,
    X_new: np.ndarray,
    threshold: float,
    consecutive_required: int = 3,
    group_ids: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    errors = reconstruction_error(model, X_new)
    raw_flags = errors > threshold
    confirmed = confirm_consecutive(raw_flags, consecutive_required=consecutive_required, group_ids=group_ids)
    return errors, raw_flags, confirmed


def load_group_ids(artifact_dir: Path, seq_len: int) -> np.ndarray | None:
    """Best-effort per-window chamber/pen id lookup for the default X_val.npy.

    Returns None when the artifact directory has no recognized metadata file,
    so callers fall back to the old ungrouped behavior.
    """
    bioenergy_val = artifact_dir / "bioenergy_val_scaled.csv"
    if bioenergy_val.exists():
        from pigproject.bioenergy_report import load_window_metadata

        metadata = load_window_metadata(bioenergy_val, seq_len=seq_len)
        return (metadata["dataset_key"].astype(str) + "_" + metadata["chamber_number"].astype(str)).to_numpy()

    activity_meta = artifact_dir / "activity_val_sequence_metadata.csv"
    if activity_meta.exists():
        df = pd.read_csv(activity_meta)
        return (df["facility_number"].astype(str) + "_" + df["pen_number"].astype(str)).to_numpy()

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect anomalies with a trained LSTM Autoencoder.")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--model-name", default="best_model.keras")
    parser.add_argument("--input", default=None, help="Optional .npy sequence array. Defaults to X_val.npy.")
    parser.add_argument("--percentile", type=float, default=99.0)
    parser.add_argument("--consecutive-required", type=int, default=3)
    parser.add_argument("--seq-len", type=int, default=24, help="Used only to look up per-window chamber/pen ids for the default X_val.npy.")
    parser.add_argument("--n-bootstrap", type=int, default=2000, help="Bootstrap resamples for the threshold confidence interval.")
    parser.add_argument("--ci-level", type=float, default=0.90, help="Confidence level for the bootstrap threshold interval.")
    parser.add_argument("--ci-warn-relative-width", type=float, default=0.5, help="Print a warning when (ci_upper - ci_lower) / threshold exceeds this fraction.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = Path(args.artifact_dir)
    model = keras.models.load_model(artifacts / args.model_name)
    X_val = np.load(artifacts / "X_val.npy")

    val_errors = reconstruction_error(model, X_val)
    threshold = float(np.percentile(val_errors, args.percentile))
    np.save(artifacts / "threshold.npy", threshold)

    ci = bootstrap_percentile_ci(
        val_errors,
        percentile=args.percentile,
        n_bootstrap=args.n_bootstrap,
        ci=args.ci_level,
    )
    pd.DataFrame([ci]).to_csv(artifacts / "threshold_confidence.csv", index=False)

    using_default_val = not args.input
    X_new = np.load(args.input) if args.input else X_val
    group_ids = load_group_ids(artifacts, seq_len=args.seq_len) if using_default_val else None
    if group_ids is not None and len(group_ids) != len(X_new):
        group_ids = None
    errors, raw_flags, confirmed_flags = detect_anomalies(
        model,
        X_new,
        threshold,
        consecutive_required=args.consecutive_required,
        group_ids=group_ids,
    )

    np.save(artifacts / "last_errors.npy", errors)
    np.save(artifacts / "last_raw_flags.npy", raw_flags)
    np.save(artifacts / "last_confirmed_flags.npy", confirmed_flags)
    print(f"threshold: {threshold:.6f}  (n={ci['n_samples']} validation windows)")
    print(
        f"{int(args.ci_level * 100)}% bootstrap CI: [{ci['ci_lower']:.6f}, {ci['ci_upper']:.6f}]"
        f"  (relative width: {ci['ci_relative_width']:.1%})"
    )
    if ci["ci_relative_width"] > args.ci_warn_relative_width:
        print(
            "WARNING: this threshold is not statistically stable at the current sample size "
            "-- treat it as provisional and prefer more validation data over trusting the point estimate."
        )
    print("raw anomaly windows:", int(raw_flags.sum()))
    print("confirmed anomaly windows:", int(confirmed_flags.sum()))


if __name__ == "__main__":
    main()
