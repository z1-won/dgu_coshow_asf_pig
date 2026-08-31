import pandas as pd

from pigproject.clearfarm_precision_tuning import (
    build_policy_masks,
    choose_recommended_policy,
    evaluate_precision_policies,
)


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "experiment": "1",
                "pen_id": "A",
                "date": pd.Timestamp("2022-01-01"),
                "baseline_alert": True,
                "candidate_alert": True,
                "added_alert": False,
                "rule_score_candidate": 0.6,
                "rule_reasons_candidate": "feed_drop",
                "candidate_reason_count": 1,
                "candidate_alert_in_previous_observed_14d": False,
                "same_reason_alert_in_previous_observed_14d": False,
                "is_jan_to_may": True,
                "any_signs_candidate": True,
            },
            {
                "experiment": "1",
                "pen_id": "A",
                "date": pd.Timestamp("2022-01-08"),
                "baseline_alert": False,
                "candidate_alert": True,
                "added_alert": True,
                "rule_score_candidate": 0.9,
                "rule_reasons_candidate": "co2_high,nh3_high,humidity_high",
                "candidate_reason_count": 3,
                "candidate_alert_in_previous_observed_14d": True,
                "same_reason_alert_in_previous_observed_14d": False,
                "is_jan_to_may": True,
                "any_signs_candidate": True,
            },
            {
                "experiment": "1",
                "pen_id": "B",
                "date": pd.Timestamp("2022-06-01"),
                "baseline_alert": False,
                "candidate_alert": True,
                "added_alert": True,
                "rule_score_candidate": 0.3,
                "rule_reasons_candidate": "co2_high,humidity_high",
                "candidate_reason_count": 2,
                "candidate_alert_in_previous_observed_14d": False,
                "same_reason_alert_in_previous_observed_14d": False,
                "is_jan_to_may": False,
                "any_signs_candidate": False,
            },
            {
                "experiment": "1",
                "pen_id": "B",
                "date": pd.Timestamp("2022-06-08"),
                "baseline_alert": False,
                "candidate_alert": False,
                "added_alert": False,
                "rule_score_candidate": 0.0,
                "rule_reasons_candidate": "",
                "candidate_reason_count": 0,
                "candidate_alert_in_previous_observed_14d": False,
                "same_reason_alert_in_previous_observed_14d": False,
                "is_jan_to_may": False,
                "any_signs_candidate": False,
            },
        ]
    )


def test_build_policy_masks_keeps_baseline_alerts_and_filters_added_candidates():
    frame = _sample_frame()

    masks = build_policy_masks(frame)

    assert masks["baseline_only"].tolist() == [True, False, False, False]
    assert masks["recall_candidate_all"].tolist() == [True, True, True, False]
    assert masks["added_high_match_reasons"].tolist() == [True, True, False, False]
    assert masks["added_score_0_6"].tolist() == [True, True, False, False]


def test_evaluate_precision_policies_reports_added_kept_and_recommended_policy():
    metrics, reason_summary = evaluate_precision_policies(_sample_frame())

    high_match = metrics[(metrics["scope"] == "all") & (metrics["policy"] == "added_high_match_reasons")].iloc[0]
    assert high_match["added_kept"] == 1
    assert high_match["added_dropped"] == 1
    assert high_match["precision"] == 1.0

    recommended = choose_recommended_policy(metrics)
    assert recommended["scope"] == "all"
    assert recommended["sensitivity"] >= 0.5
    assert len(reason_summary) == 2
