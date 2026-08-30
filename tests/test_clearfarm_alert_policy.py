import pandas as pd

from pigproject.clearfarm_alert_policy import apply_alert_policy, assign_policy_level, summarize_policy


def test_assign_policy_level_uses_three_alert_thresholds():
    assert assign_policy_level(pd.Series({"rule_score": 1.0, "environment_score": 0.0, "rule_reasons": "feed_drop"}))[1] == "cctv_focus"
    assert assign_policy_level(pd.Series({"rule_score": 0.7, "environment_score": 0.0}))[1] == "caution"
    assert assign_policy_level(pd.Series({"rule_score": 0.3, "environment_score": 0.0}))[1] == "observe"
    assert assign_policy_level(pd.Series({"rule_score": 0.0, "environment_score": 0.0}))[1] == "normal"


def test_environment_score_can_request_cctv_focus():
    rank, level, action = assign_policy_level(
        pd.Series({"rule_score": 0.3, "environment_score": 0.9, "rule_reasons": "barn_temp_high"})
    )

    assert rank == 1
    assert level == "cctv_focus"
    assert "CCTV" in action


def test_apply_alert_policy_adds_operational_flags_and_sorts():
    scored = pd.DataFrame(
        [
            {"rule_score": 0.0, "environment_score": 0.0, "management_score": 0.0, "date": "2022-01-01"},
            {"rule_score": 0.6, "environment_score": 0.0, "management_score": 0.6, "date": "2022-01-02"},
            {"rule_score": 0.9, "environment_score": 0.9, "management_score": 0.0, "date": "2022-01-03"},
        ]
    )

    policy = apply_alert_policy(scored)

    assert list(policy["policy_level"]) == ["cctv_focus", "caution", "normal"]
    assert policy.loc[0, "cctv_requested"] == True  # noqa: E712
    assert policy.loc[1, "operational_alert"] == True  # noqa: E712
    assert policy.loc[2, "operational_alert"] == False  # noqa: E712


def test_summarize_policy_reports_label_rates():
    policy = pd.DataFrame(
        [
            {"policy_level": "observe", "any_signs": True, "respiratory_signs": False, "gut_signs": False, "heat_signs": True},
            {"policy_level": "observe", "any_signs": False, "respiratory_signs": False, "gut_signs": False, "heat_signs": False},
        ]
    )

    summary = summarize_policy(policy)

    observe = summary[summary["policy_level"] == "observe"].iloc[0]
    assert observe["n_pen_days"] == 2
    assert observe["any_signs_rate"] == 0.5
