import pandas as pd

from pigproject.clearfarm_environment_policy_experiment import build_policy_comparison


def test_build_policy_comparison_reports_false_alert_burden() -> None:
    scored = pd.DataFrame(
        {
            "date": ["2022-01-01", "2022-01-02", "2022-01-03", "2022-01-04"],
            "pen_id": ["A", "A", "A", "A"],
            "temperature_max": [28.8, 30.5, 31.7, 26.0],
            "heat_signs": [False, True, True, False],
        }
    )
    candidates = pd.DataFrame(
        {
            "policy": ["screening", "balanced", "high_confidence"],
            "threshold": [28.7, 30.4, 31.6],
        }
    )

    comparison = build_policy_comparison(scored, candidates)

    screening = comparison[comparison["policy"].eq("screening")].iloc[0]
    high_conf = comparison[comparison["policy"].eq("high_confidence")].iloc[0]
    assert screening["recall"] == 1.0
    assert screening["fp"] == 1
    assert high_conf["recall"] == 0.5
    assert high_conf["false_alerts_per_100_pen_days"] == 0.0
