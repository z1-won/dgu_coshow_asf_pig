import pandas as pd

from pigproject.pig_feeding_behavior_reference import (
    compare_with_clearfarm,
    summarize_by_sex,
    summarize_distribution,
)


def _sample_df():
    return pd.DataFrame(
        [
            {"DFIkg_day": 2.0, "NDVvisits_day": 8.0, "FOmin_day": 50.0, "FIVg_visit": 250.0, "DUVmin_visit": 6.0, "FRg_min_day": 40.0, "sex": "female"},
            {"DFIkg_day": 3.0, "NDVvisits_day": 10.0, "FOmin_day": 60.0, "FIVg_visit": 300.0, "DUVmin_visit": 7.0, "FRg_min_day": 42.0, "sex": "female"},
            {"DFIkg_day": 4.0, "NDVvisits_day": 12.0, "FOmin_day": 70.0, "FIVg_visit": 350.0, "DUVmin_visit": 8.0, "FRg_min_day": 44.0, "sex": "male"},
        ]
    )


def test_summarize_distribution_computes_quantiles():
    df = _sample_df()

    summary = summarize_distribution(df, columns=["DFIkg_day"])

    row = summary.iloc[0]
    assert row["feature"] == "DFIkg_day"
    assert row["min"] == 2.0
    assert row["max"] == 4.0
    assert row["median"] == 3.0


def test_summarize_by_sex_groups_correctly():
    df = _sample_df()

    by_sex = summarize_by_sex(df, columns=["DFIkg_day"])

    female_mean = by_sex[by_sex["sex"] == "female"]["DFIkg_day_mean"].iloc[0]
    male_mean = by_sex[by_sex["sex"] == "male"]["DFIkg_day_mean"].iloc[0]
    assert female_mean == 2.5
    assert male_mean == 4.0


def test_compare_with_clearfarm_returns_none_when_file_missing(tmp_path):
    df = _sample_df()

    result = compare_with_clearfarm(df, clearfarm_feeding_day_path=tmp_path / "does_not_exist.csv")

    assert result is None


def test_compare_with_clearfarm_matches_units_when_file_present(tmp_path):
    df = _sample_df()
    clearfarm_path = tmp_path / "clearfarm_feeding_day.csv"
    pd.DataFrame({"daily_feed_intake_per_pig_kg": [2.5, 2.7, 2.9]}).to_csv(clearfarm_path, index=False)

    result = compare_with_clearfarm(df, clearfarm_feeding_day_path=clearfarm_path)

    assert result is not None
    assert set(result["source"]) == {"5126661 (개체별 요약, 육성돈)", "ClearFarm (pen-day 집계, 육성-비육돈)"}
