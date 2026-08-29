import pandas as pd

from pigproject.final_ensemble import ACTIVITY_TRACK, BIOENERGY_TRACK, build_final_table, summarize_by_chamber


def _bioenergy_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track": [BIOENERGY_TRACK, BIOENERGY_TRACK],
            "source_dataset": ["71408", "71408"],
            "chamber_id": ["bioenergy:71408:1", "bioenergy:71408:1"],
            "start_datetime": pd.to_datetime(["2023-01-01 00:00", "2023-01-01 01:00"]),
            "end_datetime": pd.to_datetime(["2023-01-01 04:00", "2023-01-01 05:00"]),
            "model_component": [0.9, 0.1],
            "rule_component": [0.9, 0.0],
            "track_score": [1.8, 0.1],
            "management_score": [0.0, 0.7],
            "environment_score": [0.0, 0.0],
            "alert_category": ["disease", "management"],
            "model_anomaly": [True, False],
            "rule_anomaly": [True, False],
            "tier": ["high", "normal"],
            "reason": ["rule: rectal_temp_high", ""],
            "low_confidence": [False, False],
        }
    )


def _activity_frame(low_confidence: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track": [ACTIVITY_TRACK],
            "source_dataset": ["622"],
            "chamber_id": ["activity622:facility1:pen1"],
            "start_datetime": pd.to_datetime(["2021-08-01 00:00"]),
            "end_datetime": pd.to_datetime(["2021-08-01 04:00"]),
            "model_component": [0.6],
            "rule_component": [0.0],
            "track_score": [0.6],
            "management_score": [0.0],
            "environment_score": [0.0],
            "alert_category": ["disease"],
            "model_anomaly": [True],
            "rule_anomaly": [False],
            "tier": ["normal"],
            "reason": ["model reconstruction error threshold 초과 (activity)"],
            "low_confidence": [low_confidence],
        }
    )


def test_build_final_table_unions_tracks_and_flags_alerts():
    combined = build_final_table([_bioenergy_frame(), _activity_frame()])

    assert len(combined) == 3
    assert set(combined["track"]) == {BIOENERGY_TRACK, ACTIVITY_TRACK}
    # sorted by track_score descending
    assert combined["track_score"].is_monotonic_decreasing
    # final_alert = model_anomaly OR rule_anomaly
    assert combined.loc[combined["chamber_id"] == "bioenergy:71408:1", "final_alert"].tolist() == [True, False]
    assert combined.loc[combined["chamber_id"] == "activity622:facility1:pen1", "final_alert"].tolist() == [True]
    assert combined.loc[combined["chamber_id"] == "bioenergy:71408:1", "operational_alert"].tolist() == [True, True]


def test_summarize_by_chamber_rolls_up_windows():
    combined = build_final_table([_bioenergy_frame(), _activity_frame()])
    summary = summarize_by_chamber(combined)

    bioenergy_row = summary[summary["chamber_id"] == "bioenergy:71408:1"].iloc[0]
    assert bioenergy_row["windows"] == 2
    assert bioenergy_row["max_score"] == 1.8
    assert bioenergy_row["alert_windows"] == 1
    assert bioenergy_row["high_tier_windows"] == 1
    assert bioenergy_row["chamber_tier"] == "high"

    activity_row = summary[summary["chamber_id"] == "activity622:facility1:pen1"].iloc[0]
    assert activity_row["windows"] == 1
    assert activity_row["chamber_tier"] == "normal"


def test_summarize_by_chamber_propagates_low_confidence_flag():
    combined = build_final_table([_bioenergy_frame(), _activity_frame(low_confidence=True)])
    summary = summarize_by_chamber(combined)

    bioenergy_row = summary[summary["chamber_id"] == "bioenergy:71408:1"].iloc[0]
    activity_row = summary[summary["chamber_id"] == "activity622:facility1:pen1"].iloc[0]
    assert bioenergy_row["low_confidence"] == False  # noqa: E712
    assert activity_row["low_confidence"] == True  # noqa: E712
