import pandas as pd

from pigproject.farm_event_schema import (
    evaluate_lead_time,
    filter_alerts_by_category,
    match_events_to_alerts,
    summarize_lead_time,
    validate_events,
)


def test_validate_events_accepts_required_schema():
    df = pd.DataFrame(
        {
            "event_id": ["evt-1"],
            "farm_id": ["farm-a"],
            "chamber_id": ["bioenergy:71408:1"],
            "event_type": ["fever"],
            "start_datetime": ["2023-01-01 08:00:00"],
            "end_datetime": ["2023-01-01 18:00:00"],
            "severity": [3],
            "vet_confirmed": ["false"],
            "source": ["farm_log"],
            "notes": ["test"],
        }
    )

    result = validate_events(df)

    assert result.issues.empty
    assert result.cleaned.loc[0, "vet_confirmed"] == False  # noqa: E712


def test_validate_events_reports_schema_errors():
    df = pd.DataFrame(
        {
            "event_id": ["evt-1", "evt-1"],
            "farm_id": ["farm-a", ""],
            "chamber_id": ["bioenergy:71408:1", "bioenergy:71408:1"],
            "event_type": ["bad-type", "fever"],
            "start_datetime": ["2023-01-02", "2023-01-01"],
            "end_datetime": ["2023-01-01", "2023-01-02"],
            "severity": [6, 2],
            "vet_confirmed": ["maybe", "true"],
            "source": ["farm_log", "farm_log"],
            "notes": ["test", "test"],
        }
    )

    result = validate_events(df)

    assert set(result.issues["column"]) >= {"event_id", "event_type", "end_datetime", "severity", "vet_confirmed"}


def test_match_events_to_alerts_uses_chamber_and_time_overlap():
    events = pd.DataFrame(
        {
            "event_id": ["evt-1", "evt-2"],
            "farm_id": ["farm-a", "farm-a"],
            "chamber_id": ["bioenergy:71408:1", "bioenergy:71408:2"],
            "event_type": ["fever", "fever"],
            "start_datetime": pd.to_datetime(["2023-01-01 08:00", "2023-01-01 08:00"]),
            "end_datetime": pd.to_datetime(["2023-01-01 18:00", "2023-01-01 18:00"]),
            "severity": [3, 3],
            "vet_confirmed": [False, False],
            "source": ["farm_log", "farm_log"],
            "notes": ["test", "test"],
        }
    )
    alerts = pd.DataFrame(
        {
            "track": ["bioenergy", "bioenergy"],
            "chamber_id": ["bioenergy:71408:1", "bioenergy:71408:1"],
            "start_datetime": ["2023-01-01 10:00", "2023-01-03 10:00"],
            "end_datetime": ["2023-01-01 12:00", "2023-01-03 12:00"],
            "track_score": [1.2, 1.5],
            "tier": ["medium", "high"],
            "reason": ["model", "rule"],
            "final_alert": [True, True],
        }
    )

    matches = match_events_to_alerts(events, alerts)

    assert len(matches) == 1
    assert matches.loc[0, "event_id"] == "evt-1"
    assert matches.loc[0, "overlap_hours"] == 2.0


def test_evaluate_lead_time_finds_alerts_before_event_start():
    events = pd.DataFrame(
        {
            "event_id": ["evt-1"],
            "farm_id": ["farm-a"],
            "chamber_id": ["bioenergy:71408:1"],
            "event_type": ["fever"],
            "start_datetime": pd.to_datetime(["2023-01-04 00:00"]),
            "end_datetime": pd.to_datetime(["2023-01-04 12:00"]),
            "severity": [4],
            "vet_confirmed": [True],
            "source": ["farm_log"],
            "notes": ["test"],
            "expected_rule": ["rectal_temp_high"],
        }
    )
    alerts = pd.DataFrame(
        {
            "track": ["bioenergy", "bioenergy", "bioenergy", "bioenergy"],
            "chamber_id": [
                "bioenergy:71408:1",
                "bioenergy:71408:1",
                "bioenergy:71408:1",
                "bioenergy:71408:2",
            ],
            "start_datetime": [
                "2023-01-03 12:00",
                "2022-12-31 23:00",
                "2023-01-04 01:00",
                "2023-01-03 12:00",
            ],
            "end_datetime": [
                "2023-01-03 13:00",
                "2023-01-01 00:00",
                "2023-01-04 02:00",
                "2023-01-03 13:00",
            ],
            "track_score": [1.2, 1.5, 1.9, 1.8],
            "tier": ["medium", "high", "high", "high"],
            "reason": ["within 24h", "outside 72h", "after event", "wrong chamber"],
            "final_alert": [True, True, True, True],
        }
    )

    lead_matches, event_summary = evaluate_lead_time(events, alerts, horizons_hours=(24, 48, 72))

    assert len(lead_matches) == 1
    assert lead_matches.loc[0, "lead_hours"] == 12.0
    assert lead_matches.loc[0, "matched_horizons_hours"] == "24,48,72"
    assert event_summary.loc[0, "caught_within_24h"] == True  # noqa: E712
    assert event_summary.loc[0, "first_lead_hours"] == 12.0
    assert event_summary.loc[0, "expected_rule"] == "rectal_temp_high"


def test_summarize_lead_time_reports_recall_and_precision_proxy():
    lead_event_summary = pd.DataFrame(
        {
            "event_id": ["evt-1", "evt-2"],
            "event_type": ["fever", "respiratory"],
            "lead_alert_count": [1, 0],
            "first_lead_hours": [12.0, pd.NA],
            "caught_within_24h": [True, False],
            "caught_within_48h": [True, False],
            "caught_within_72h": [True, False],
        }
    )
    lead_matches = pd.DataFrame(
        {
            "chamber_id": ["bioenergy:71408:1"],
            "alert_start_datetime": ["2023-01-03 12:00"],
            "alert_end_datetime": ["2023-01-03 13:00"],
        }
    )
    alerts = pd.DataFrame(
        {
            "chamber_id": ["bioenergy:71408:1", "bioenergy:71408:2"],
            "final_alert": [True, True],
        }
    )

    metrics = summarize_lead_time(lead_event_summary, lead_matches, alerts, horizons_hours=(24, 48, 72))
    all_row = metrics[metrics["scope"] == "all"].iloc[0]

    assert all_row["events"] == 2
    assert all_row["lead_matched_events"] == 1
    assert all_row["recall_24h"] == 0.5
    assert all_row["precision_proxy"] == 0.5


def test_filter_alerts_by_category_uses_alert_category_tokens():
    alerts = pd.DataFrame(
        {
            "alert_category": ["disease", "management,environment", "", pd.NA],
            "final_alert": [True, True, False, False],
            "operational_alert": [True, True, True, False],
        }
    )

    assert len(filter_alerts_by_category(alerts, "disease")) == 1
    assert len(filter_alerts_by_category(alerts, "management")) == 1
    assert len(filter_alerts_by_category(alerts, "environment")) == 1
    assert len(filter_alerts_by_category(alerts, "final")) == 2
    assert len(filter_alerts_by_category(alerts, "operational")) == 3
