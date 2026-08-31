import pandas as pd

from pigproject.clearfarm_action_queue_adapter import (
    adapt_policy_to_action_input,
    build_yolo_focus_input,
    categories_from_reasons,
    tier_from_policy,
)


def test_categories_from_reasons_maps_management_and_environment():
    assert categories_from_reasons("feed_drop") == "management"
    assert categories_from_reasons("co2_high,nh3_high") == "environment"
    assert categories_from_reasons("feed_drop,barn_temp_high") == "management,environment"


def test_tier_from_policy_maps_three_levels():
    assert tier_from_policy("cctv_focus") == "high"
    assert tier_from_policy("caution") == "medium"
    assert tier_from_policy("observe") == "watch"
    assert tier_from_policy("normal") == "normal"


def test_adapt_policy_to_action_input_matches_common_schema():
    policy = pd.DataFrame(
        [
            {
                "date": "2022-07-19",
                "experiment": 3,
                "pen_id": "F2.3",
                "rule_score": 2.1,
                "management_score": 0.6,
                "environment_score": 1.2,
                "rule_reasons": "feed_drop,nh3_high,barn_temp_high",
                "policy_level": "cctv_focus",
                "operational_alert": True,
                "cctv_requested": True,
                "recommended_action": "CCTV 집중 확인",
                "environment_temp_policy": "high_confidence",
                "environment_temp_label": "고확신",
                "environment_temp_action": "CCTV/현장 확인 우선순위",
            }
        ]
    )

    out = adapt_policy_to_action_input(policy)

    assert out.loc[0, "track"] == "clearfarm_rule_policy"
    assert out.loc[0, "environment_temp_label"] == "고확신"
    assert out.loc[0, "source_dataset"] == "ClearFarm"
    assert out.loc[0, "chamber_id"] == "clearfarm:exp3:penF2.3"
    assert out.loc[0, "track_score"] == 2.1
    assert out.loc[0, "alert_category"] == "management,environment"
    assert out.loc[0, "tier"] == "high"
    assert out.loc[0, "rule_anomaly"] == True  # noqa: E712
    assert "policy:cctv_focus" in out.loc[0, "reason"]


def test_adapt_policy_to_action_input_tolerates_missing_temperature_policy_columns():
    policy = pd.DataFrame(
        [
            {
                "date": "2022-07-19",
                "experiment": 3,
                "pen_id": "F2.3",
                "rule_score": 0.3,
                "management_score": 0.0,
                "environment_score": 0.3,
                "rule_reasons": "co2_high",
                "policy_level": "observe",
                "operational_alert": True,
                "cctv_requested": False,
                "recommended_action": "관찰",
            }
        ]
    )

    out = adapt_policy_to_action_input(policy)

    assert out.loc[0, "environment_temp_policy"] == ""
    assert out.loc[0, "environment_temp_label"] == ""
    assert out.loc[0, "environment_temp_action"] == ""


def test_build_yolo_focus_input_keeps_only_cctv_requested_rows():
    action_input = pd.DataFrame(
        [
            {
                "source_dataset": "ClearFarm",
                "chamber_id": "clearfarm:exp3:penF2.3",
                "start_datetime": "2022-07-19",
                "end_datetime": "2022-07-19 23:59:59",
                "policy_level": "cctv_focus",
                "track_score": 1.2,
                "management_score": 0.6,
                "environment_score": 0.3,
                "alert_category": "management,environment",
                "reason": "policy:cctv_focus rule: management: feed_drop",
                "recommended_action": "CCTV 집중 확인",
                "cctv_requested": True,
            },
            {
                "source_dataset": "ClearFarm",
                "chamber_id": "clearfarm:exp3:penA1.3",
                "start_datetime": "2022-07-20",
                "end_datetime": "2022-07-20 23:59:59",
                "policy_level": "observe",
                "track_score": 0.3,
                "management_score": 0.0,
                "environment_score": 0.3,
                "alert_category": "environment",
                "reason": "policy:observe rule: environment: co2_high",
                "recommended_action": "관찰",
                "cctv_requested": False,
            },
        ]
    )

    out = build_yolo_focus_input(action_input)

    assert len(out) == 1
    assert out.loc[0, "policy_level"] == "cctv_focus"
