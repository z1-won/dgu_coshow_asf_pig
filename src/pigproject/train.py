"""Train the LSTM Autoencoder."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from tensorflow import keras

from pigproject.model import build_lstm_autoencoder


def train_model(
    artifact_dir: str | Path = "artifacts",
    latent_dim: int = 32,
    epochs: int = 100,
    batch_size: int = 32,
    resume_model: str | Path | None = None,
) -> keras.Model:
    artifacts = Path(artifact_dir)
    X_train = np.load(artifacts / "X_train.npy")
    X_val = np.load(artifacts / "X_val.npy")

    if X_train.size == 0 or X_val.size == 0:
        raise ValueError("Empty sequence array. Lower seq_len or provide a longer normal-data period.")

    if resume_model:
        model_path = Path(resume_model)
        if not model_path.is_absolute():
            model_path = artifacts / model_path
        model = keras.models.load_model(model_path)
        print(f"Resuming from {model_path}")
    else:
        model = build_lstm_autoencoder(
            seq_len=X_train.shape[1],
            n_features=X_train.shape[2],
            latent_dim=latent_dim,
        )
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True),
        keras.callbacks.ModelCheckpoint(artifacts / "best_model.keras", monitor="val_loss", save_best_only=True),
    ]
    model.fit(
        X_train,
        X_train,
        validation_data=(X_val, X_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        shuffle=True,
    )
    model.save(artifacts / "final_model.keras")
    if resume_model:
        model.save(artifacts / "continued_model.keras")
    return model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train LSTM Autoencoder.")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--latent-dim", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--resume-model", default=None, help="Existing .keras model to continue training.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_model(
        artifact_dir=args.artifact_dir,
        latent_dim=args.latent_dim,
        epochs=args.epochs,
        batch_size=args.batch_size,
        resume_model=args.resume_model,
    )
    print("Saved best_model.keras and final_model.keras.")


if __name__ == "__main__":
    main()
