import pandas as pd
import pytest

from pigproject.clearfarm_rule_scorecard import add_rule_scores, best_rows, score_sweep
from pigproject.clearfarm_rule_validation import RuleThresholds


def test_add_rule_scores_weights_hits_and_cooccurrence_bonus():
    df = pd.DataFrame(
        [
            {
                "feed_intake_daily_min_zscore_3d": -2.0,
                "co2_max": 3000.0,
                "ammonia_max": 30.0,
                "temperature_max": 32.0,
                "humidity_max": 80.0,
            },
            {
                "feed_intake_daily_min_zscore_3d": 0.0,
                "co2_max": 1000.0,
                "ammonia_max": 5.0,
                "temperature_max": 20.0,
                "humidity_max": 60.0,
            },
        ]
    )
    thresholds = RuleThresholds(feed_drop=-1.5, co2_high=2500.0, nh3_high=29.0, barn_temp_high=31.0)

    scored = add_rule_scores(df, thresholds)

    assert scored.loc[0, "rule_triggered_count"] == 4
    assert scored.loc[0, "management_score"] == 0.6
    assert scored.loc[0, "environment_score"] == pytest.approx(1.8)
    assert scored.loc[0, "rule_score"] == pytest.approx(2.7)
    assert scored.loc[1, "rule_score"] == 0.0


def test_add_rule_scores_uses_optional_humidity_candidate():
    df = pd.DataFrame(
        [
            {
                "feed_intake_daily_min_zscore_3d": 0.0,
                "co2_max": 1000.0,
                "ammonia_max": 5.0,
                "temperature_max": 20.0,
                "humidity_max": 82.0,
            }
        ]
    )
    thresholds = RuleThresholds(co2_high=2500.0, humidity_high=75.0)

    scored = add_rule_scores(df, thresholds)

    assert scored.loc[0, "rule_humidity_high"] == True  # noqa: E712
    assert scored.loc[0, "environment_score"] == 0.3
    assert scored.loc[0, "rule_reasons"] == "humidity_high"


def test_score_sweep_scores_thresholds_against_sign_column():
    df = pd.DataFrame(
        [
            {"rule_score": 1.2, "any_signs": True},
            {"rule_score": 1.2, "any_signs": False},
            {"rule_score": 0.0, "any_signs": True},
            {"rule_score": 0.0, "any_signs": False},
        ]
    )

    sweep = score_sweep(df, "rule_score", "any_signs", [0.8])

    assert sweep.loc[0, "tp"] == 1
    assert sweep.loc[0, "fp"] == 1
    assert sweep.loc[0, "fn"] == 1
    assert sweep.loc[0, "tn"] == 1


def test_best_rows_picks_best_f1_per_score_and_sign():
    sweeps = pd.DataFrame(
        [
            {"score_col": "rule_score", "sign_col": "any_signs", "threshold": 0.3, "f1": 0.2, "precision": 0.2, "sensitivity": 0.2},
            {"score_col": "rule_score", "sign_col": "any_signs", "threshold": 0.8, "f1": 0.5, "precision": 0.4, "sensitivity": 0.7},
        ]
    )

    best = best_rows(sweeps)

    assert len(best) == 1
    assert best.loc[0, "threshold"] == 0.8
