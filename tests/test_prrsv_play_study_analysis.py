import pandas as pd

from pigproject.prrsv_play_study_analysis import (
    activity_shift_summary,
    confusion_for_threshold,
    per_pig_timeline,
)


def test_confusion_for_threshold_scores_symptomatic_days():
    df = pd.DataFrame(
        [
            {"rectal_temp_c": 40.0, "clinical_score": 2},
            {"rectal_temp_c": 38.5, "clinical_score": 2},
            {"rectal_temp_c": 40.0, "clinical_score": 0},
            {"rectal_temp_c": 38.5, "clinical_score": 0},
        ]
    )

    result = confusion_for_threshold(df, threshold=39.5)

    assert result["tp"] == 1
    assert result["fn"] == 1
    assert result["fp"] == 1
    assert result["tn"] == 1
    assert result["sensitivity"] == 0.5


def test_per_pig_timeline_finds_first_events_and_lags():
    df = pd.DataFrame(
        [
            {
                "pig_id": "1",
                "treatment": "play",
                "dpi": 0,
                "rectal_temp_c": 38.5,
                "clinical_score": 0,
                "viral_load_log10": 0,
                "treated": False,
            },
            {
                "pig_id": "1",
                "treatment": "play",
                "dpi": 5,
                "rectal_temp_c": 39.0,
                "clinical_score": 1,
                "viral_load_log10": 10,
                "treated": False,
            },
            {
                "pig_id": "1",
                "treatment": "play",
                "dpi": 6,
                "rectal_temp_c": 40.0,
                "clinical_score": 3,
                "viral_load_log10": 11,
                "treated": True,
            },
        ]
    )

    timeline = per_pig_timeline(df, threshold=39.5)
    row = timeline.iloc[0]

    assert row["first_symptom_dpi"] == 5
    assert row["first_temp_rule_dpi"] == 6
    assert row["first_treatment_dpi"] == 6
    assert row["temp_lag_vs_symptom_dpi"] == 1
    assert row["treatment_lag_vs_symptom_dpi"] == 1


def test_activity_shift_summary_compares_symptomatic_vs_healthy():
    df = pd.DataFrame(
        [
            {"symptomatic": False, "active_count": 4.0, "inactive_count": 10.0},
            {"symptomatic": False, "active_count": 4.0, "inactive_count": 10.0},
            {"symptomatic": True, "active_count": 2.0, "inactive_count": 14.0},
            {"symptomatic": True, "active_count": 2.0, "inactive_count": 14.0},
        ]
    )

    summary = activity_shift_summary(df).set_index("feature")

    assert summary.loc["active_count", "healthy_mean"] == 4.0
    assert summary.loc["active_count", "symptomatic_mean"] == 2.0
    assert summary.loc["active_count", "relative_change"] == -0.5
    assert summary.loc["inactive_count", "relative_change"] == 0.4
