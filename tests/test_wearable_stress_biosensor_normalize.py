import numpy as np
import pandas as pd

from pigproject.wearable_stress_biosensor_normalize import (
    FEATURE_COLUMNS,
    add_condition,
    load_source,
    mask_sentinels,
    sentinel_summary,
)


def _raw_row(**overrides):
    row = {
        "Animal": "pig1",
        "Time": "2021-11-26 15:50:25",
        "Activity": "bfandaf_iso",
        "HR": 65.0,
        "BR": 10.0,
        "SkinTemp": -3276.8,
        "CoreTemp": 38.0,
        "Posture": 97.0,
        "PeakAccel": 0.49,
        "Vertical": 2000.0,
        "Lateral": 2000.0,
        "Sagittal": 2000.0,
        "ECGAmplitude": 0.001,
        "ECGNoise": 0.0001,
        "GSR": 65535.0,
        "RtoR": 700.5,
        "HRV": 65535.0,
        "BRAmplitude": 100.0,
        "DeviceTemp": 21.1,
    }
    row.update(overrides)
    return row


def test_load_source_parses_datetime_and_sorts_by_pig_and_time(tmp_path):
    path = tmp_path / "s1.csv"
    rows = [
        _raw_row(Animal="pig2", Time="2021-11-26 15:50:26"),
        _raw_row(Animal="pig1", Time="2021-11-26 15:50:25"),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

    df = load_source(path)

    assert list(df["pig_id"]) == ["pig1", "pig2"]
    assert df["datetime"].iloc[0] == pd.Timestamp("2021-11-26 15:50:25")
    assert "SkinTemp" not in df.columns
    assert "GSR" not in df.columns


def test_mask_sentinels_replaces_known_sentinel_values_only(tmp_path):
    path = tmp_path / "s1.csv"
    pd.DataFrame([_raw_row(HR=0.0, CoreTemp=6553.5)]).to_csv(path, index=False)
    df = load_source(path)

    cleaned = mask_sentinels(df)

    assert np.isnan(cleaned["heart_rate"].iloc[0])
    assert np.isnan(cleaned["hrv"].iloc[0])
    assert np.isnan(cleaned["core_temp"].iloc[0])
    assert cleaned["breath_rate"].iloc[0] == 10.0
    assert set(FEATURE_COLUMNS).issubset(cleaned.columns)


def test_add_condition_matches_paper_categorize_activity_rule(tmp_path):
    path = tmp_path / "s1.csv"
    rows = [
        _raw_row(Animal="pig1", Activity="af_isoandpair"),
        _raw_row(Animal="pig1", Activity="bfandaf_iso"),
        _raw_row(Animal="pig1", Activity="bfandaf_isoandpair"),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    df = load_source(path)

    labeled = add_condition(df)

    assert list(labeled["condition"]) == ["Pair", "Isolation", "Pair"]


def test_sentinel_summary_reports_full_sentinel_columns(tmp_path):
    path = tmp_path / "s1.csv"
    pd.DataFrame([_raw_row(), _raw_row()]).to_csv(path, index=False)
    df = load_source(path)

    summary = sentinel_summary(df).set_index("feature")

    assert summary.loc["hrv", "sentinel_pct"] == 100.0
    assert summary.loc["heart_rate", "sentinel_pct"] == 0.0
