import pandas as pd

from pigproject.rule_threshold_experiment import _recommend_experiment, apply_threshold_overrides, summarize_result


def test_apply_threshold_overrides_copies_and_updates_matching_rules():
    rules = [
        {"id": "co2_high", "threshold": 1000, "feature": "CO2_mean"},
        {"id": "nh3_high", "threshold": 10, "feature": "NH3_mean"},
    ]

    updated = apply_threshold_overrides(rules, {"co2_high": 1200})

    assert updated[0]["threshold"] == 1200
    assert updated[1]["threshold"] == 10
    assert rules[0]["threshold"] == 1000


def test_summarize_result_counts_alert_categories():
    result = pd.DataFrame(
        {
            "rule_observation": [True, True, False],
            "rule_anomaly": [True, False, False],
            "final_alert": [True, True, False],
            "disease_alert": [True, False, False],
            "management_alert": [False, True, False],
            "environment_alert": [False, False, False],
            "disease_score": [1.2, 0.4, 0.1],
            "primary_reason": ["rule: disease: rectal_temp_high", "rule: management: feed_drop", ""],
        }
    )

    summary = summarize_result("candidate", {"co2_high": 1200}, result)

    assert summary["experiment"] == "candidate"
    assert summary["overrides"] == "co2_high=1200"
    assert summary["windows"] == 3
    assert summary["final_alert"] == 2
    assert summary["disease_alert"] == 1
    assert summary["management_alert"] == 1
    assert summary["top_reason"] == "rule: disease: rectal_temp_high"


def test_recommend_experiment_keeps_disease_and_reduces_environment():
    row = pd.Series({"experiment": "co2_1200", "disease_alert_delta": 0, "environment_alert_delta": -6, "final_alert_delta": -6})
    assert _recommend_experiment(row) == "candidate_environment_tightening"

    reject = pd.Series({"experiment": "bad", "disease_alert_delta": -1, "environment_alert_delta": -6, "final_alert_delta": -7})
    assert _recommend_experiment(reject) == "reject_disease_loss"
