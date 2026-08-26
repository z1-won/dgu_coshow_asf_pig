"""LSTM Autoencoder for chamber-level time-series reconstruction."""

from __future__ import annotations

from tensorflow import keras
from tensorflow.keras import layers


def build_lstm_autoencoder(seq_len: int, n_features: int, latent_dim: int = 32) -> keras.Model:
    inputs = keras.Input(shape=(seq_len, n_features))

    encoded = layers.LSTM(64, activation="tanh", return_sequences=True)(inputs)
    encoded = layers.LSTM(latent_dim, activation="tanh", return_sequences=False)(encoded)

    decoded = layers.RepeatVector(seq_len)(encoded)
    decoded = layers.LSTM(latent_dim, activation="tanh", return_sequences=True)(decoded)
    decoded = layers.LSTM(64, activation="tanh", return_sequences=True)(decoded)
    outputs = layers.TimeDistributed(layers.Dense(n_features))(decoded)

    model = keras.Model(inputs, outputs, name="lstm_autoencoder")
    model.compile(optimizer="adam", loss="mse")
    return model
