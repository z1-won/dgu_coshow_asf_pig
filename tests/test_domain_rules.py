import pandas as pd

from pigproject.domain_rules import evaluate_rules


def test_evaluate_rules_supports_management_drop_rules():
    window_table = pd.DataFrame(
        {
            "dataset_key": ["71408", "71408"],
            "chamber_number": [1, 1],
            "start_datetime": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "end_datetime": pd.to_datetime(["2023-01-01 04:00", "2023-01-02 04:00"]),
            "feedstuff_volume_mean_zscore_3d__wmean": [-2.0, 0.0],
            "watersupply_mean_zscore_3d__wmean": [-1.8, 0.2],
        }
    )
    rules = [
        {
            "id": "feed_drop",
            "feature": "feedstuff_volume_mean_zscore_3d",
            "agg": "mean",
            "op": "<=",
            "threshold": -1.5,
            "severity": "medium",
            "category": "management",
        },
        {
            "id": "water_drop",
            "feature": "watersupply_mean_zscore_3d",
            "agg": "mean",
            "op": "<=",
            "threshold": -1.5,
            "severity": "medium",
            "category": "management",
        },
    ]

    result = evaluate_rules(window_table, rules)

    assert result.loc[0, "rule_feed_drop"] == True  # noqa: E712
    assert result.loc[0, "rule_water_drop"] == True  # noqa: E712
    assert result.loc[0, "management_rule_anomaly"] == True  # noqa: E712
    assert result.loc[0, "disease_rule_anomaly"] == False  # noqa: E712
    assert result.loc[0, "rule_triggered_count"] == 2
    assert result.loc[0, "rule_score"] > result.loc[0, "rule_severity_sum"]
    assert result.loc[1, "rule_anomaly"] == False  # noqa: E712


def test_evaluate_rules_supports_all_of_composite_rules():
    window_table = pd.DataFrame(
        {
            "dataset_key": ["71408", "71408"],
            "chamber_number": [1, 1],
            "start_datetime": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "end_datetime": pd.to_datetime(["2023-01-01 04:00", "2023-01-02 04:00"]),
            "ventilation_rate_mean__wmean": [1.2, 1.2],
            "CO2_mean__wmax": [1000, 800],
        }
    )
    rules = [
        {
            "id": "ventilation_low_with_co2_high",
            "severity": "medium",
            "all_of": [
                {
                    "feature": "ventilation_rate_mean",
                    "agg": "mean",
                    "op": "<=",
                    "threshold": 1.5,
                },
                {
                    "feature": "CO2_mean",
                    "agg": "max",
                    "op": ">=",
                    "threshold": 950,
                },
            ],
        }
    ]

    result = evaluate_rules(window_table, rules)

    assert result.loc[0, "rule_ventilation_low_with_co2_high"] == True  # noqa: E712
    assert result.loc[1, "rule_ventilation_low_with_co2_high"] == False  # noqa: E712


def test_low_severity_rule_is_observation_not_final_rule_anomaly():
    window_table = pd.DataFrame(
        {
            "dataset_key": ["71408"],
            "chamber_number": [1],
            "start_datetime": pd.to_datetime(["2023-01-01"]),
            "end_datetime": pd.to_datetime(["2023-01-01 04:00"]),
            "CO2_mean__wmax": [1000],
        }
    )
    rules = [
        {
            "id": "co2_high",
            "feature": "CO2_mean",
            "agg": "max",
            "op": ">=",
            "threshold": 950,
            "severity": "low",
            "category": "environment",
        }
    ]

    result = evaluate_rules(window_table, rules)

    assert result.loc[0, "rule_observation"] == True  # noqa: E712
    assert result.loc[0, "rule_anomaly"] == False  # noqa: E712
    assert result.loc[0, "environment_rule_anomaly"] == False  # noqa: E712


def test_evaluate_rules_supports_min_aggregation_for_short_drop_signal():
    window_table = pd.DataFrame(
        {
            "dataset_key": ["71408", "71408"],
            "chamber_number": [1, 1],
            "start_datetime": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "end_datetime": pd.to_datetime(["2023-01-01 04:00", "2023-01-02 04:00"]),
            "feedstuff_volume_mean_zscore_3d__wmean": [-0.3, -0.2],
            "feedstuff_volume_mean_zscore_3d__wmin": [-1.8, -0.7],
        }
    )
    rules = [
        {
            "id": "feed_drop",
            "feature": "feedstuff_volume_mean_zscore_3d",
            "agg": "min",
            "op": "<=",
            "threshold": -1.5,
            "severity": "medium",
            "category": "management",
        }
    ]

    result = evaluate_rules(window_table, rules)

    assert result.loc[0, "rule_feed_drop"] == True  # noqa: E712
    assert result.loc[0, "management_rule_anomaly"] == True  # noqa: E712
    assert result.loc[1, "rule_feed_drop"] == False  # noqa: E712
