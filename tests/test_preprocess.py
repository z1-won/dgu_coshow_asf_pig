from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.preprocess import build_time_index, create_sequences, resample_per_chamber


def test_build_time_index_from_date_time():
    df = pd.DataFrame(
        {
            "chamber_number": ["A"],
            "date": ["260101"],
            "time": ["0010"],
            "timestamp": [np.nan],
        }
    )

    result = build_time_index(df)

    assert result["datetime"].iloc[0].year == 2026
    assert result["datetime"].iloc[0].minute == 10


def test_resample_and_sequence_creation():
    rows = []
    for idx in range(4):
        rows.append(
            {
                "chamber_number": "A",
                "datetime": pd.Timestamp("2026-01-01 00:00") + pd.Timedelta(minutes=10 * idx),
                "rectal_temperature": 38.5,
                "back_temperature": 37.0,
                "neck_temperature": 37.2,
                "head_temperature": 36.9,
                "T": 24,
                "RH": 60,
                "CO2": 500,
                "NH3": 3,
                "breath_rate": 25,
                "distance": idx,
                "ventilation_rate": 1,
                "feedstuff_volume": 2,
                "watersupply": 3,
            }
        )

    resampled = resample_per_chamber(pd.DataFrame(rows), freq="10min")
    sequences = create_sequences(resampled, seq_len=3)

    assert len(resampled) == 4
    assert sequences.shape == (2, 3, 13)
