from pathlib import Path

import pandas as pd

from pigproject.environment_weakness_plan import build_environment_weakness_plan, choose_clearfarm_candidates


def test_choose_clearfarm_candidates_returns_three_policy_rows() -> None:
    sweep = pd.DataFrame(
        {
            "threshold": [27.3, 28.7, 30.4, 31.6],
            "sensitivity": [1.0, 0.9, 0.8, 0.5],
            "specificity": [0.5, 0.8, 0.92, 0.97],
            "precision": [0.1, 0.2, 0.36, 0.48],
            "f1": [0.18, 0.31, 0.49, 0.47],
            "fp": [300, 150, 58, 21],
        }
    )

    candidates = choose_clearfarm_candidates(sweep)

    assert set(candidates["policy"]) == {"screening", "balanced", "high_confidence"}
    assert candidates.loc[candidates["policy"].eq("balanced"), "threshold"].iloc[0] == 30.4
    assert candidates.loc[candidates["policy"].eq("screening"), "threshold"].iloc[0] == 28.7


def test_build_environment_weakness_plan_writes_outputs(tmp_path: Path) -> None:
    clearfarm = pd.DataFrame(
        {
            "threshold": [28.7, 30.4, 31.6],
            "sensitivity": [0.925, 0.8, 0.475],
            "specificity": [0.785, 0.921, 0.972],
            "precision": [0.189, 0.356, 0.475],
            "f1": [0.314, 0.492, 0.475],
            "fp": [159, 58, 21],
        }
    )
    hotpig = pd.DataFrame(
        {
            "split": ["TN_validation", "HS_test"],
            "confirmed_anomaly_rate": [0.01, 0.12],
        }
    )
    sowell = pd.DataFrame(
        {
            "scope": ["environment_heat", "environment_cold"],
            "during_recall": [1.0, 1.0],
        }
    )
    clearfarm_path = tmp_path / "clearfarm.csv"
    hotpig_path = tmp_path / "hotpig.csv"
    sowell_path = tmp_path / "sowell.csv"
    clearfarm.to_csv(clearfarm_path, index=False)
    hotpig.to_csv(hotpig_path, index=False)
    sowell.to_csv(sowell_path, index=False)

    candidates, evidence, report = build_environment_weakness_plan(clearfarm_path, hotpig_path, sowell_path, tmp_path / "out")

    assert report.exists()
    assert len(candidates) == 3
    assert "SOWELL" in evidence["evidence_source"].str.cat(sep=" ")
    assert (tmp_path / "out" / "environment_threshold_candidates.csv").exists()
