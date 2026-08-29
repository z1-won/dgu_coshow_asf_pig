import pandas as pd

from pigproject.asf_dryad_analysis import confusion_for_threshold, per_pig_timeline


def test_confusion_for_threshold_scores_symptomatic_days():
    df = pd.DataFrame(
        [
            {"rectal_temp": 40.0, "clinical_score": 2},
            {"rectal_temp": 38.5, "clinical_score": 2},
            {"rectal_temp": 40.0, "clinical_score": 0},
            {"rectal_temp": 38.5, "clinical_score": 0},
        ]
    )

    result = confusion_for_threshold(df, threshold=39.5)

    assert result["tp"] == 1
    assert result["fn"] == 1
    assert result["fp"] == 1
    assert result["tn"] == 1
    assert result["sensitivity"] == 0.5


def test_per_pig_timeline_finds_first_events():
    df = pd.DataFrame(
        [
            {
                "pig_id": "Farm pig #1",
                "cohort": "Farm",
                "day_post_challenge": 0,
                "rectal_temp": 38.5,
                "clinical_score": 0,
                "viral_load_blood": 10,
                "leukocytes": 12.0,
            },
            {
                "pig_id": "Farm pig #1",
                "cohort": "Farm",
                "day_post_challenge": 5,
                "rectal_temp": 39.0,
                "clinical_score": 1,
                "viral_load_blood": 10,
                "leukocytes": 8.0,
            },
            {
                "pig_id": "Farm pig #1",
                "cohort": "Farm",
                "day_post_challenge": 6,
                "rectal_temp": 40.0,
                "clinical_score": 3,
                "viral_load_blood": 1000,
                "leukocytes": 5.0,
            },
        ]
    )

    timeline = per_pig_timeline(df, threshold=39.5)
    row = timeline.iloc[0]

    assert row["first_symptom_day"] == 5
    assert row["first_temp_rule_day"] == 6
    assert row["first_viral_detected_day"] == 6
    assert row["temp_lag_vs_symptom_day"] == 1
