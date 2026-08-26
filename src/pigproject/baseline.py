"""Isolation Forest baseline for fast anomaly-detection sanity checks."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest


def flatten_sequences(X: np.ndarray) -> np.ndarray:
    if X.ndim != 3:
        raise ValueError(f"Expected (samples, seq_len, features), got {X.shape}")
    return X.reshape((X.shape[0], X.shape[1] * X.shape[2]))


def train_baseline(
    artifact_dir: str | Path = "artifacts",
    contamination: float = 0.01,
    random_state: int = 42,
) -> IsolationForest:
    artifacts = Path(artifact_dir)
    X_train = flatten_sequences(np.load(artifacts / "X_train.npy"))
    X_val = flatten_sequences(np.load(artifacts / "X_val.npy"))

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train)

    scores = -model.score_samples(X_val)
    flags = model.predict(X_val) == -1
    joblib.dump(model, artifacts / "isolation_forest.joblib")
    np.save(artifacts / "iforest_val_scores.npy", scores)
    np.save(artifacts / "iforest_val_flags.npy", flags)
    print("validation anomaly windows:", int(flags.sum()))
    return model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Isolation Forest baseline.")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--contamination", type=float, default=0.01)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_baseline(
        artifact_dir=args.artifact_dir,
        contamination=args.contamination,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    main()
