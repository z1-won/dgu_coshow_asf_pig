import numpy as np
import pandas as pd

from pigproject.clearfarm_baseline import (
    FEATURE_COLUMNS,
    build_sequence_metadata,
    create_sequences_for_pen,
    fit_transform_per_pen_scaler,
    split_normal_train_val,
)


def _rows(pen_id, n, status_by_index=None):
    status_by_index = status_by_index or {}
    rows = []
    for i in range(n):
        row = {feature: float(i) for feature in FEATURE_COLUMNS}
        row.update(
            {
                "pen_id": pen_id,
                "date": pd.Timestamp("2021-01-01") + pd.Timedelta(days=i),
                "day_status": status_by_index.get(i, "unobserved"),
            }
        )
        rows.append(row)
    return rows


def test_build_sequence_metadata_and_create_sequences_stay_aligned():
    df = pd.DataFrame(_rows("A2.1", 5, {4: "symptomatic"}))

    metadata = build_sequence_metadata(df, seq_len=3)
    sequences = create_sequences_for_pen(df, FEATURE_COLUMNS, seq_len=3)

    assert len(metadata) == len(sequences) == 3
    assert metadata.iloc[-1]["day_status"] == "symptomatic"
    assert metadata.iloc[-1]["window_end_index"] == 4


def test_split_normal_train_val_only_uses_normal_ending_windows():
    metadata = pd.DataFrame(
        [
            {"pen_id": "A2.1", "end_date": pd.Timestamp("2021-01-01") + pd.Timedelta(days=i), "day_status": status}
            for i, status in enumerate(["normal"] * 8 + ["symptomatic"] * 2)
        ]
    )

    train_idx, val_idx, summary = split_normal_train_val(metadata, train_ratio=0.75)

    assert len(train_idx) == 6
    assert len(val_idx) == 2
    assert metadata.loc[train_idx]["day_status"].eq("normal").all()
    assert metadata.loc[val_idx]["day_status"].eq("normal").all()
    assert summary.iloc[0]["status"] == "ok"


def test_fit_transform_per_pen_scaler_normalizes_each_pen_independently():
    all_normal = {i: "normal" for i in range(4)}
    df = pd.DataFrame(_rows("A2.1", 4, all_normal) + _rows("B3.1", 4, all_normal))
    df[FEATURE_COLUMNS[0]] = [10.0, 20.0, 30.0, 40.0, 1000.0, 2000.0, 3000.0, 4000.0]

    scaled, scalers = fit_transform_per_pen_scaler(df, FEATURE_COLUMNS)

    assert set(scalers.keys()) == {"A2.1", "B3.1"}
    pen_a = scaled[scaled["pen_id"] == "A2.1"][FEATURE_COLUMNS[0]]
    pen_b = scaled[scaled["pen_id"] == "B3.1"][FEATURE_COLUMNS[0]]
    assert np.isclose(pen_a.mean(), 0.0, atol=1e-6)
    assert np.isclose(pen_b.mean(), 0.0, atol=1e-6)
