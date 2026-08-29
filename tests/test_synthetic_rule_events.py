import pandas as pd

from pigproject.synthetic_rule_events import build_synthetic_event_sets


def test_build_synthetic_event_sets_splits_positive_negative_and_mixed():
    flags = pd.DataFrame(
        {
            "dataset_key": ["71408", "71408", "71408"],
            "chamber_number": [4, 2, 1],
            "start_datetime": ["2022-11-28 14:34:00", "2022-12-13 11:15:00", "2022-11-17 18:02:00"],
            "end_datetime": ["2022-12-05 13:41:00", "2022-12-20 10:43:00", "2022-12-31 15:52:00"],
            "disease_score": [1.9, 1.2, 1.1],
            "rule_reasons": ["rectal_temp_high,co2_high", "rectal_temp_high", "co2_high,nh3_high"],
        }
    )

    sets = build_synthetic_event_sets(flags)

    assert len(sets["synthetic_rule_positive_events.csv"]) == 3
    assert len(sets["synthetic_rule_negative_events.csv"]) == 3
    assert len(sets["synthetic_mixed_events.csv"]) == 6
    assert set(sets["synthetic_rule_positive_events.csv"]["event_type"]) == {
        "fever",
        "respiratory",
        "environment_failure",
    }
