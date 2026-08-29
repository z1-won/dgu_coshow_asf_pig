from pathlib import Path

import pandas as pd

from pigproject.external_validation_summary import (
    build_external_validation_summary,
    write_external_validation_report,
)


def test_external_validation_summary_keeps_behavior_auxiliary(tmp_path: Path) -> None:
    behavior = pd.DataFrame(
        [
            {
                "profile": "behavior_only",
                "hs_confirmed_anomaly_rate": 0.03,
            },
            {
                "profile": "behavior_muscle",
                "hs_confirmed_anomaly_rate": 1.0,
            },
            {
                "profile": "full",
                "hs_confirmed_anomaly_rate": 1.0,
            },
        ]
    )
    hotpig = pd.DataFrame(
        [
            {
                "split": "TN_validation",
                "confirmed_anomaly_rate": 0.01,
            },
            {
                "split": "HS_test",
                "confirmed_anomaly_rate": 0.12,
            },
        ]
    )
    asf = pd.DataFrame(
        [
            {
                "threshold": 39.5,
                "sensitivity": 0.49,
                "specificity": 0.99,
                "precision": 0.95,
            }
        ]
    )

    behavior_path = tmp_path / "behavior.csv"
    hotpig_path = tmp_path / "hotpig.csv"
    asf_path = tmp_path / "asf.csv"
    behavior.to_csv(behavior_path, index=False)
    hotpig.to_csv(hotpig_path, index=False)
    asf.to_csv(asf_path, index=False)

    summary = build_external_validation_summary(behavior_path, hotpig_path, asf_path)

    behavior_row = summary[summary["dataset"] == "Behavior x Heat Tolerance"].iloc[0]
    assert behavior_row["priority"] == 3
    assert "auxiliary" in behavior_row["project_decision"]
    assert "Do not mix directly" in behavior_row["do_not_use_for"]


def test_write_external_validation_report(tmp_path: Path) -> None:
    summary = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "HOTPIG",
                "validation_role": "sanity",
                "main_result": "result",
                "project_decision": "decision",
                "do_not_use_for": "limit",
                "next_action": "next",
            }
        ]
    )

    report_path = write_external_validation_report(summary, tmp_path)

    assert report_path.exists()
    assert (tmp_path / "external_validation_summary.csv").exists()
    assert "외부 검증 데이터 통합 요약" in report_path.read_text(encoding="utf-8")
