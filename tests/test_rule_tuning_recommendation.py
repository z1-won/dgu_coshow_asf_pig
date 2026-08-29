import pandas as pd

from pigproject.rule_tuning_recommendation import (
    build_rule_feedback,
    extract_rule_ids,
    load_rule_config,
    write_outputs,
)


def _rule_config() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rule_id": ["rectal_temp_high", "feed_drop", "co2_high", "nh3_high"],
            "category": ["disease", "management", "environment", "environment"],
            "severity": ["high", "medium", "low", "low"],
            "feature": ["rectal_temperature_mean_corrected", "feedstuff_volume_mean_zscore_3d", "CO2_mean", "NH3_mean"],
            "op": [">=", "<=", ">=", ">="],
            "threshold": [39.5, -1.5, 1000, 10],
            "is_composite": [False, False, False, False],
            "note": ["", "", "", ""],
        }
    )


def _review_log() -> pd.DataFrame:
    rows = []
    for idx in range(3):
        rows.append(
            {
                "incident_id": f"environment-{idx + 1:04d}",
                "queue": "environment",
                "review_status": "false_alarm",
                "confirmed": False,
                "false_alarm": True,
                "actual_cause": "sensor_error",
                "reason": "rule: environment: co2_high,nh3_high",
                "max_track_score": 0.2,
                "max_management_score": 0.0,
                "max_environment_score": 0.9,
            }
        )
    for idx in range(3):
        rows.append(
            {
                "incident_id": f"disease-{idx + 1:04d}",
                "queue": "disease",
                "review_status": "confirmed",
                "confirmed": True,
                "false_alarm": False,
                "actual_cause": "fever",
                "reason": "rule: disease: rectal_temp_high",
                "max_track_score": 1.2,
                "max_management_score": 0.0,
                "max_environment_score": 0.0,
            }
        )
    rows.append(
        {
            "incident_id": "management-0001",
            "queue": "management",
            "review_status": "pending",
            "confirmed": pd.NA,
            "false_alarm": pd.NA,
            "actual_cause": "",
            "reason": "rule: management: feed_drop",
            "max_track_score": 0.2,
            "max_management_score": 0.6,
            "max_environment_score": 0.0,
        }
    )
    return pd.DataFrame(rows)


def test_extract_rule_ids_from_reason():
    rule_ids = extract_rule_ids(
        "rule: disease: rectal_temp_high ; environment: co2_high",
        {"rectal_temp_high", "co2_high", "feed_drop"},
    )

    assert rule_ids == ["rectal_temp_high", "co2_high"]


def test_build_rule_feedback_recommends_from_review_outcomes():
    recommendations = build_rule_feedback(_review_log(), _rule_config())

    co2 = recommendations[recommendations["rule_id"] == "co2_high"].iloc[0]
    rectal = recommendations[recommendations["rule_id"] == "rectal_temp_high"].iloc[0]
    feed = recommendations[recommendations["rule_id"] == "feed_drop"].iloc[0]

    assert co2["recommendation"] == "tighten_threshold"
    assert co2["false_alarm_rate"] == 1.0
    assert rectal["recommendation"] == "keep_or_relax_carefully"
    assert rectal["confirmed_rate"] == 1.0
    assert feed["recommendation"] == "collect_more_reviews"


def test_build_rule_feedback_ignores_auxiliary_rules_from_other_queues():
    review_log = pd.DataFrame(
        {
            "incident_id": ["disease-0001"],
            "queue": ["disease"],
            "review_status": ["confirmed"],
            "confirmed": [True],
            "false_alarm": [False],
            "actual_cause": ["fever"],
            "reason": ["rule: disease: rectal_temp_high ; environment: co2_high"],
            "max_track_score": [1.2],
            "max_management_score": [0.0],
            "max_environment_score": [0.3],
        }
    )
    recommendations = build_rule_feedback(review_log, _rule_config())

    rectal = recommendations[recommendations["rule_id"] == "rectal_temp_high"].iloc[0]
    co2 = recommendations[recommendations["rule_id"] == "co2_high"].iloc[0]
    assert rectal["reviewed"] == 1
    assert co2["reviewed"] == 0


def test_load_rule_config_and_write_outputs(tmp_path):
    config_path = tmp_path / "domain_rules.json"
    config_path.write_text(
        '{"rules":[{"id":"feed_drop","category":"management","severity":"medium","feature":"x","op":"<=","threshold":-1.5}]}',
        encoding="utf-8",
    )
    rule_config = load_rule_config(config_path)
    recommendations = build_rule_feedback(_review_log(), rule_config)
    output, report = write_outputs(recommendations, tmp_path / "recommendations.csv", tmp_path / "report.md")

    assert pd.read_csv(output).shape[0] == 1
    assert "Rule Tuning Recommendation" in report.read_text(encoding="utf-8")
