import pandas as pd

from pigproject.aihub_71471_baseline import (
    create_labeled_sequences,
    fit_global_normal_scaler,
    split_sequence_sets,
    transform_global_scaler,
)


def test_split_sequence_sets_uses_estrus_only_as_label() -> None:
    metadata = pd.DataFrame(
        {
            "split": ["training", "training", "validation", "validation"],
            "estrus_ratio_max": [0.0, 1.0, 0.0, 1.0],
        }
    )
    sequences = pd.Series([0, 1, 2, 3]).to_numpy()

    sets = split_sequence_sets(sequences, metadata)

    assert sets["train_normal"][0].tolist() == [0]
    assert sets["val_normal"][0].tolist() == [2]
    assert sets["val_estrus"][0].tolist() == [3]


def test_create_labeled_sequences_tracks_window_estrus_ratio() -> None:
    df = pd.DataFrame(
        {
            "farm_id": ["farm"] * 3,
            "channel": [1] * 3,
            "split": ["training"] * 3,
            "datetime": pd.date_range("2022-01-01", periods=3, freq="10min"),
            "estrus_ratio": [0.0, 1.0, 1.0],
            "injected_ratio": [0.0, 0.0, 1.0],
            "feature": [1.0, 2.0, 3.0],
        }
    )

    sequences, metadata = create_labeled_sequences(df, ["feature"], seq_len=2)

    assert sequences.shape == (2, 2, 1)
    assert metadata.loc[0, "estrus_ratio_mean"] == 0.5
    assert metadata.loc[1, "estrus_ratio_max"] == 1.0


def test_global_scaler_can_transform_estrus_only_channels() -> None:
    train_normal = pd.DataFrame({"farm_id": ["farm"], "channel": [9], "feature": [10.0]})
    all_rows = pd.DataFrame(
        {
            "farm_id": ["farm", "farm"],
            "channel": [9, 1],
            "feature": [10.0, 20.0],
        }
    )
    scaler = fit_global_normal_scaler(train_normal, ["feature"])

    transformed = transform_global_scaler(all_rows, ["feature"], scaler)

    assert len(transformed) == 2
    assert transformed.loc[0, "feature"] == 0.0
