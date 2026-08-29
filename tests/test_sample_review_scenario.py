import pandas as pd

from pigproject.incident_review import build_review_log_template, summarize_review_log
from pigproject.rule_tuning_recommendation import build_rule_feedback
from pigproject.sample_review_scenario import build_sample_review_log


def _incident_queue() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "incident_id": ["disease-0001", "disease-0002", "environment-0001", "management-0001"],
            "queue": ["disease", "disease", "environment", "management"],
            "priority": ["high", "high", "high", "watch"],
            "chamber_id": ["c1", "c2", "c3", "c4"],
            "incident_start_datetime": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
            "incident_end_datetime": ["2023-01-01 04:00", "2023-01-02 04:00", "2023-01-03 04:00", "2023-01-04 04:00"],
            "window_count": [2, 2, 1, 1],
            "max_track_score": [1.2, 1.1, 0.2, 0.2],
            "max_management_score": [0.0, 0.0, 0.0, 0.6],
            "max_environment_score": [0.0, 0.0, 0.9, 0.0],
            "reason": [
                "rule: disease: rectal_temp_high",
                "rule: disease: rectal_temp_high",
                "rule: environment: co2_high,nh3_high",
                "rule: management: feed_drop",
            ],
            "recommended_action": ["vet", "vet", "ventilation", "feed"],
        }
    )


def _rule_config() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rule_id": ["rectal_temp_high", "co2_high", "nh3_high", "feed_drop"],
            "category": ["disease", "environment", "environment", "management"],
            "severity": ["high", "low", "low", "medium"],
            "feature": ["temp", "co2", "nh3", "feed"],
            "op": [">=", ">=", ">=", "<="],
            "threshold": [39.5, 1000, 10, -1.5],
            "is_composite": [False, False, False, False],
            "note": ["", "", "", ""],
        }
    )


def test_build_sample_review_log_fills_deterministic_outcomes():
    template = build_review_log_template(_incident_queue())
    sample = build_sample_review_log(template)

    assert sample["review_status"].value_counts().to_dict() == {"confirmed": 3, "false_alarm": 1}
    assert sample[sample["queue"] == "environment"]["actual_cause"].iloc[0] == "sensor_error"
    assert sample[sample["queue"] == "management"]["actual_cause"].iloc[0] == "feed_or_water_supply_issue"


def test_sample_review_log_changes_summary_and_recommendations():
    template = build_review_log_template(_incident_queue())
    sample = build_sample_review_log(template)
    summary = summarize_review_log(sample)
    recommendations = build_rule_feedback(sample, _rule_config())

    all_row = summary[summary["scope"] == "all"].iloc[0]
    rectal = recommendations[recommendations["rule_id"] == "rectal_temp_high"].iloc[0]
    co2 = recommendations[recommendations["rule_id"] == "co2_high"].iloc[0]

    assert all_row["reviewed"] == 4
    assert all_row["precision_estimate"] == 0.75
    assert rectal["recommendation"] == "collect_more_reviews"
    assert co2["false_alarm"] == 1
