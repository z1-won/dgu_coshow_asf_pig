import pandas as pd

from pigproject.clearfarm_rule_validation import (
    RuleThresholds,
    compute_feed_zscore_3d,
    confusion_for_composite,
    confusion_for_threshold,
    define_disease_signs,
    filter_health_observed,
    threshold_sweep,
    write_composite_report,
)


def test_filter_health_observed_drops_days_without_observation():
    df = pd.DataFrame(
        [
            {"pen_id": "A1", "date": "2021-01-01", "health_observation_rows": 11.0},
            {"pen_id": "A1", "date": "2021-01-02", "health_observation_rows": float("nan")},
            {"pen_id": "A1", "date": "2021-01-03", "health_observation_rows": 0.0},
        ]
    )

    observed = filter_health_observed(df)

    assert len(observed) == 1
    assert observed.iloc[0]["date"] == "2021-01-01"


def test_define_disease_signs_flags_respiratory_gut_thermal_and_any():
    df = pd.DataFrame(
        [
            {"cough_sum": 5.0, "sneeze_sum": 0.0, "pump_sum": 0.0, "diar_sum": 0.0, "pant_sum": 0.0, "shiv_sum": 0.0},
            {"cough_sum": 0.0, "sneeze_sum": 0.0, "pump_sum": 0.0, "diar_sum": 2.0, "pant_sum": 0.0, "shiv_sum": 0.0},
            {"cough_sum": 0.0, "sneeze_sum": 0.0, "pump_sum": 0.0, "diar_sum": 0.0, "pant_sum": 3.0, "shiv_sum": 0.0},
            {"cough_sum": 0.0, "sneeze_sum": 0.0, "pump_sum": 0.0, "diar_sum": 0.0, "pant_sum": 0.0, "shiv_sum": 0.0},
        ]
    )

    out = define_disease_signs(df)

    assert list(out["respiratory_signs"]) == [True, False, False, False]
    assert list(out["gut_signs"]) == [False, True, False, False]
    assert list(out["heat_signs"]) == [False, False, True, False]
    assert list(out["cold_signs"]) == [False, False, False, False]
    assert list(out["any_signs"]) == [True, True, True, False]


def test_compute_feed_zscore_3d_matches_production_rolling_features():
    # Same semantics as rolling_features.add_rolling_features: an inclusive
    # calendar-time 3-day window (today counts), not a trailing/excluding one.
    df = pd.DataFrame(
        [
            {"pen_id": "A1", "date": pd.Timestamp("2021-01-01"), "daily_feed_intake_per_pig_kg": 2.0},
            {"pen_id": "A1", "date": pd.Timestamp("2021-01-02"), "daily_feed_intake_per_pig_kg": 3.0},
            {"pen_id": "A1", "date": pd.Timestamp("2021-01-03"), "daily_feed_intake_per_pig_kg": 4.0},
            {"pen_id": "A1", "date": pd.Timestamp("2021-01-04"), "daily_feed_intake_per_pig_kg": 0.0},
        ]
    )

    out = compute_feed_zscore_3d(df)

    assert out.iloc[0]["feedstuff_volume_mean_zscore_3d"] == 0.0  # single-point window, no variance
    assert round(out.iloc[1]["feedstuff_volume_mean_zscore_3d"], 4) == 0.7071
    assert out.iloc[2]["feedstuff_volume_mean_zscore_3d"] == 1.0
    assert round(out.iloc[3]["feedstuff_volume_mean_zscore_3d"], 4) == -1.1209


def test_compute_feed_zscore_3d_zeroes_out_zero_variance_windows():
    # A pen with 3 identical days must not blow up to +-inf: the std==0
    # guard in add_rolling_features should zero the z-score instead.
    df = pd.DataFrame(
        [
            {"pen_id": "B1", "date": pd.Timestamp("2021-01-01"), "daily_feed_intake_per_pig_kg": 3.0},
            {"pen_id": "B1", "date": pd.Timestamp("2021-01-02"), "daily_feed_intake_per_pig_kg": 3.0},
            {"pen_id": "B1", "date": pd.Timestamp("2021-01-03"), "daily_feed_intake_per_pig_kg": 3.0},
        ]
    )

    out = compute_feed_zscore_3d(df)

    assert (out["feedstuff_volume_mean_zscore_3d"] == 0.0).all()


def test_confusion_for_threshold_flags_drops_below_threshold():
    df = pd.DataFrame(
        [
            {"z": -2.0, "sign": True},
            {"z": -2.0, "sign": False},
            {"z": 0.0, "sign": True},
            {"z": 0.0, "sign": False},
        ]
    )

    result = confusion_for_threshold(df, "z", threshold=-1.0, sign_col="sign")

    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1
    assert result["sensitivity"] == 0.5


def test_threshold_sweep_runs_one_confusion_matrix_per_threshold():
    df = pd.DataFrame([{"z": -2.0, "sign": True}, {"z": 0.0, "sign": False}])

    sweep = threshold_sweep(df, "z", thresholds=[-1.0, -0.5], sign_col="sign")

    assert list(sweep["threshold"]) == [-1.0, -0.5]
    assert (sweep["n"] == 2).all()


def test_confusion_for_threshold_direction_above_flags_high_values():
    df = pd.DataFrame(
        [
            {"co2": 1200.0, "sign": True},
            {"co2": 1200.0, "sign": False},
            {"co2": 500.0, "sign": True},
            {"co2": 500.0, "sign": False},
        ]
    )

    result = confusion_for_threshold(df, "co2", threshold=1000, sign_col="sign", direction="above")

    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1


def test_confusion_for_composite_scores_a_precombined_boolean_series():
    df = pd.DataFrame(
        [
            {"any_signs": True},
            {"any_signs": False},
            {"any_signs": True},
            {"any_signs": False},
        ]
    )
    rule_hit = pd.Series([True, True, False, False])

    result = confusion_for_composite(df, rule_hit, "any_signs")

    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1


def test_write_composite_report_uses_passed_thresholds(tmp_path):
    df = pd.DataFrame(
        [
            {"feed_intake_daily_min_zscore_3d": -2.0, "co2_max": 3000.0, "temperature_max": 32.0, "any_signs": True},
            {"feed_intake_daily_min_zscore_3d": 0.0, "co2_max": 1000.0, "temperature_max": 20.0, "any_signs": False},
        ]
    )
    thresholds = RuleThresholds(feed_drop=-1.5, co2_high=2500.0, barn_temp_high=31.0, source="test-config")

    report = write_composite_report(tmp_path, df, thresholds)
    summary = pd.read_csv(tmp_path / "clearfarm_composite_rules_vs_any_signs.csv")

    assert report.exists()
    assert summary.loc[summary["rule"] == "co2_high", "n_fires"].iloc[0] == 1
    assert summary.loc[summary["rule"] == "barn_temp_high", "n_fires"].iloc[0] == 1
    assert "test-config" in report.read_text(encoding="utf-8")
