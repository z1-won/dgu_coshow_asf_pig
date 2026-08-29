import pandas as pd

from pigproject.rule_upgrade_compare import summarize_rule_result


def test_summarize_rule_result_counts_alerts_and_tiers():
    df = pd.DataFrame(
        {
            "rule_observation": [True, True, False],
            "rule_anomaly": [True, False, False],
            "final_alert": [True, False, True],
            "disease_alert": [True, False, True],
            "management_alert": [False, True, False],
            "environment_alert": [False, False, True],
            "disease_tier": ["high", "normal", "medium"],
            "disease_score": [1.8, 0.4, 1.0],
        }
    )

    summary = summarize_rule_result("rules", df)

    assert summary["rule_set"] == "rules"
    assert summary["windows"] == 3
    assert summary["rule_observation"] == 2
    assert summary["rule_anomaly"] == 1
    assert summary["final_alert"] == 2
    assert summary["disease_alert"] == 2
    assert summary["management_alert"] == 1
    assert summary["environment_alert"] == 1
    assert summary["high_tier"] == 1
    assert summary["medium_tier"] == 1
