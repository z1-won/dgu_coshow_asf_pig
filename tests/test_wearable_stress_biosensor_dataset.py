import numpy as np
import pandas as pd

from pigproject.wearable_stress_biosensor_dataset import (
    FEATURE_COLUMNS,
    build_sequence_metadata,
    fit_transform_global_pair_scaler,
    load_source,
    resample_to_10min,
    split_pair_train_val,
)
from pigproject.wearable_stress_biosensor_normalize import FEATURE_COLUMNS as RAW_FEATURE_COLUMNS


def _raw_row(**overrides):
    row = {feature: 1.0 for feature in RAW_FEATURE_COLUMNS}
    row.update(
        {
            "pig_id": "pig1",
            "datetime": pd.Timestamp("2026-01-01 00:00:00"),
            "condition": "Pair",
            "raw_activity_label": "bfandaf_isoandpair",
        }
    )
    row.update(overrides)
    return row


def test_resample_to_10min_builds_mean_and_std_features(tmp_path):
    path = tmp_path / "features.csv"
    rows = []
    for idx in range(20):
        rows.append(
            _raw_row(
                datetime=pd.Timestamp("2026-01-01 00:00:00") + pd.Timedelta(seconds=idx),
                heart_rate=60.0 + idx,
            )
        )
    pd.DataFrame(rows).to_csv(path, index=False)

    source = load_source(path)
    resampled = resample_to_10min(source)

    assert len(resampled) == 1
    assert set(FEATURE_COLUMNS).issubset(resampled.columns)
    assert resampled["heart_rate_mean"].iloc[0] == np.mean([60.0 + idx for idx in range(20)])
    assert resampled["heart_rate_std"].iloc[0] == np.std([60.0 + idx for idx in range(20)], ddof=1)


def test_split_pair_train_val_skips_animal_without_pair_rows():
    rows = []
    for pig_id, condition, count in [("pig13", "Pair", 60), ("pig11", "Isolation", 60)]:
        for idx in range(count):
            rows.append(
                {
                    "pig_id": pig_id,
                    "datetime": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=10 * idx),
                    "condition": condition,
                    **{feature: 1.0 for feature in FEATURE_COLUMNS},
                }
            )
    df = pd.DataFrame(rows)

    train_df, val_df, summary = split_pair_train_val(df, train_ratio=0.5, seq_len=5)

    assert set(train_df["pig_id"]) == {"pig13"}
    assert set(val_df["pig_id"]) == {"pig13"}
    assert "pig11" not in summary["pig_id"].tolist()


def test_global_pair_scaler_can_transform_isolation_only_animal():
    base = {feature: 1.0 for feature in FEATURE_COLUMNS}
    train = pd.DataFrame([{**base, "pig_id": "pig13"}])
    val = pd.DataFrame([{**base, "pig_id": "pig13"}])
    isolation = pd.DataFrame([{**base, "pig_id": "pig11"}])

    _, _, isolation_scaled, scaler = fit_transform_global_pair_scaler(train, val, isolation)

    assert scaler.mean_.shape[0] == len(FEATURE_COLUMNS)
    assert isolation_scaled[FEATURE_COLUMNS].notna().all().all()


def test_build_sequence_metadata_matches_create_sequences_window_order():
    rows = []
    for pig_id in ["pig13", "pig15"]:
        for idx in range(4):
            rows.append(
                {
                    "dataset_key": "wearable_stress_biosensor",
                    "chamber_number": pig_id,
                    "datetime": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=10 * idx),
                    "condition": "Isolation",
                }
            )
    df = pd.DataFrame(rows)

    metadata = build_sequence_metadata(df, seq_len=3)

    assert len(metadata) == 4  # 2 windows per pig x 2 pigs
    assert list(metadata["pig_id"]) == ["pig13", "pig13", "pig15", "pig15"]
    assert metadata.iloc[0]["window_start_index"] == 0
    assert metadata.iloc[0]["window_end_index"] == 2
