import pandas as pd

from pigproject.category_lead_time_report import build_category_lead_time_metrics


def test_build_category_lead_time_metrics_splits_alert_categories():
    events = pd.DataFrame(
        {
            "event_id": ["e1", "e2"],
            "farm_id": ["farm", "farm"],
            "chamber_id": ["c1", "c1"],
            "event_type": ["fever", "environment_failure"],
            "expected_rule": ["rectal_temp_high", "co2_high"],
            "start_datetime": pd.to_datetime(["2023-01-02 00:00", "2023-01-02 00:00"]),
            "end_datetime": pd.to_datetime(["2023-01-02 06:00", "2023-01-02 06:00"]),
            "severity": [3, 3],
            "vet_confirmed": [True, True],
        }
    )
    alerts = pd.DataFrame(
        {
            "track": ["bioenergy", "bioenergy"],
            "chamber_id": ["c1", "c1"],
            "start_datetime": ["2023-01-01 12:00", "2023-01-01 12:00"],
            "end_datetime": ["2023-01-01 13:00", "2023-01-01 13:00"],
            "track_score": [1.0, 0.2],
            "tier": ["medium", "normal"],
            "reason": ["disease", "environment"],
            "alert_category": ["disease", "environment"],
            "final_alert": [True, True],
            "operational_alert": [True, True],
        }
    )

    metrics, events_by_category = build_category_lead_time_metrics(
        events,
        alerts,
        categories=("disease", "environment"),
        horizons_hours=(24,),
    )

    all_rows = metrics[metrics["scope"] == "all"].set_index("alert_category_filter")
    assert all_rows.loc["disease", "recall_24h"] == 1.0
    assert all_rows.loc["environment", "recall_24h"] == 1.0
    assert set(events_by_category["alert_category_filter"]) == {"disease", "environment"}
