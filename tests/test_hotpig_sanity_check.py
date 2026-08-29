import pandas as pd

from pigproject.hotpig_sanity_check import (
    build_sequence_metadata,
    feature_columns,
    resample_pig_series,
)


def test_resample_pig_series_builds_10min_features():
    rows = []
    for idx in range(10):
        rows.append(
            {
                "datetime": pd.Timestamp("2026-01-01 00:00") + pd.Timedelta(minutes=idx),
                "pig_id": "P1",
                "conditions": "TN",
                "feed": 1.0,
                "unknown": 0,
                "standing": 150 if idx < 5 else 0,
                "seating": 0,
                "lying": 0 if idx < 5 else 150,
                "eating": 0,
                "drinking": 0,
                "cuddling": 0,
                "curious": 0,
                "idle": 0,
                "drink": 0,
                "eat": 0,
                "mate": 0,
            }
        )
    out = resample_pig_series(pd.DataFrame(rows))

    assert len(out) == 1
    assert out["standing_frac"].iloc[0] == 0.5
    assert out["lying_frac"].iloc[0] == 0.5
    assert out["feed"].iloc[0] == 10.0


def test_build_sequence_metadata_matches_window_count():
    rows = []
    for idx in range(5):
        rows.append(
            {
                "dataset_key": "hotpig",
                "chamber_number": "P1",
                "conditions": "HS",
                "datetime": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=10 * idx),
                **{feature: 0.0 for feature in feature_columns()},
            }
        )
    metadata = build_sequence_metadata(pd.DataFrame(rows), seq_len=3)

    assert len(metadata) == 3
    assert metadata["pig_id"].tolist() == ["P1", "P1", "P1"]
    assert metadata["condition"].tolist() == ["HS", "HS", "HS"]
