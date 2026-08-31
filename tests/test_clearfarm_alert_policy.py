import pandas as pd

from pigproject.clearfarm_alert_policy import (
    apply_alert_policy,
    assign_environment_policy,
    assign_policy_level,
    attach_precision_policy,
    summarize_policy,
    write_policy_outputs,
)


def test_assign_environment_policy_maps_temperature_candidates():
    assert assign_environment_policy(pd.Series({"temperature_max": 28.8}))[:2] == ("screening", "선별")
    assert assign_environment_policy(pd.Series({"temperature_max": 30.4}))[:2] == ("balanced", "균형")
    assert assign_environment_policy(pd.Series({"temperature_max": 31.6}))[:2] == ("high_confidence", "고확신")
    assert assign_environment_policy(pd.Series({"temperature_max": 27.0}))[:2] == ("normal", "정상 범위")



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


def test_precision_filter_demotes_added_candidate_to_observe():
    rank, level, action = assign_policy_level(
        pd.Series(
            {
                "rule_score": 0.9,
                "environment_score": 0.9,
                "rule_reasons": "co2_high,nh3_high",
                "precision_policy_alert": False,
            }
        )
    )

    assert rank == 3
    assert level == "observe"
    assert "반복" in action


def test_apply_alert_policy_adds_operational_flags_and_sorts():
    scored = pd.DataFrame(
        [
            {"rule_score": 0.0, "environment_score": 0.0, "management_score": 0.0, "temperature_max": 27.0, "date": "2022-01-01"},
            {"rule_score": 0.6, "environment_score": 0.0, "management_score": 0.6, "temperature_max": 30.5, "date": "2022-01-02"},
            {"rule_score": 0.9, "environment_score": 0.9, "management_score": 0.0, "temperature_max": 31.7, "date": "2022-01-03"},
        ]
    )

    policy = apply_alert_policy(scored)

    assert list(policy["policy_level"]) == ["cctv_focus", "caution", "normal"]
    assert policy.loc[0, "cctv_requested"] == True  # noqa: E712
    assert policy.loc[1, "operational_alert"] == True  # noqa: E712
    assert policy.loc[2, "operational_alert"] == False  # noqa: E712
    assert policy.loc[0, "environment_temp_policy"] == "high_confidence"
    assert policy.loc[1, "environment_temp_policy"] == "balanced"


def test_attach_precision_policy_marks_suppressed_added_alerts():
    scored = pd.DataFrame(
        [
            {
                "experiment": "1",
                "pen_id": "A",
                "date": "2022-01-01",
                "rule_score": 0.9,
                "environment_score": 0.9,
                "management_score": 0.0,
                "rule_reasons": "co2_high,nh3_high",
            }
        ]
    )
    precision_frame = pd.DataFrame(
        [
            {
                "experiment": "1",
                "pen_id": "A",
                "date": "2022-01-01",
                "baseline_alert": False,
                "candidate_alert": True,
                "added_alert": True,
                "rule_score_candidate": 0.9,
                "rule_reasons_candidate": "co2_high,nh3_high",
                "candidate_reason_count": 2,
                "candidate_alert_in_previous_observed_14d": False,
                "same_reason_alert_in_previous_observed_14d": False,
            }
        ]
    )

    attached = attach_precision_policy(scored, precision_frame)

    assert attached.loc[0, "precision_policy_alert"] == False  # noqa: E712
    assert attached.loc[0, "precision_suppressed"] == True  # noqa: E712


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


def test_write_policy_outputs_without_precision_frame(tmp_path):
    policy = apply_alert_policy(
        pd.DataFrame(
            [
                {
                    "rule_score": 0.9,
                    "environment_score": 0.9,
                    "management_score": 0.0,
                    "temperature_max": 31.7,
                    "rule_reasons": "barn_temp_high",
                    "date": "2022-01-01",
                    "experiment": "1",
                    "pen_id": "A",
                    "any_signs": True,
                    "respiratory_signs": False,
                    "gut_signs": False,
                    "heat_signs": True,
                }
            ]
        )
    )

    policy_path, summary_path, report_path = write_policy_outputs(policy, tmp_path)

    assert policy_path.exists()
    assert summary_path.exists()
    assert report_path.exists()
    assert "환경 온도 해석" in report_path.read_text(encoding="utf-8")

