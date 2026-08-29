import pandas as pd

from pigproject.synthetic_management_scenario import (
    build_management_events,
    build_synthetic_management_rule_flags,
)


def test_build_synthetic_management_rule_flags_injects_feed_and_water_alerts():
    flags = pd.DataFrame(
        {
            "dataset_key": ["71408", "71408", "71408"],
            "chamber_number": [1, 1, 1],
            "start_datetime": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "end_datetime": ["2023-01-01 04:00", "2023-01-02 04:00", "2023-01-03 04:00"],
            "final_alert": [False, False, True],
            "model_component": [0.1, 0.2, 0.3],
            "alert_category": ["", "", "disease"],
        }
    )

    injected = build_synthetic_management_rule_flags(flags)
    management = injected[injected["alert_category"] == "management"]

    assert len(management) == 2
    assert set(management["management_rule_reasons"]) == {"feed_drop", "water_drop"}
    assert management["management_alert"].all()
    assert not management["disease_alert"].any()


def test_build_management_events_uses_injected_alert_start():
    flags = pd.DataFrame(
        {
            "dataset_key": ["71408"],
            "chamber_number": [1],
            "start_datetime": ["2023-01-01 00:00"],
            "end_datetime": ["2023-01-01 04:00"],
            "alert_category": ["management"],
            "management_rule_reasons": ["feed_drop"],
        }
    )

    events = build_management_events(flags)

    assert len(events) == 1
    assert events.loc[0, "event_type"] == "feed_drop"
    assert str(events.loc[0, "start_datetime"]) == "2023-01-01 20:00:00"
