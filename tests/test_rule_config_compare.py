import pandas as pd

from pigproject.rule_config_compare import write_report


def test_write_report_persists_summary_and_reason_compare(tmp_path):
    results = {
        "summary": pd.DataFrame(
            {
                "experiment": ["baseline_config", "candidate_config"],
                "final_alert": [26, 20],
                "disease_alert": [20, 20],
                "environment_alert": [6, 0],
                "final_alert_delta": [0, -6],
                "disease_alert_delta": [0, 0],
                "environment_alert_delta": [0, -6],
                "top_reason": ["rule: environment: co2_high|nh3_high", "rule: disease: rectal_temp_high"],
            }
        ),
        "reason_compare": pd.DataFrame(
            {
                "primary_reason": ["rule: environment: co2_high|nh3_high"],
                "baseline_alerts": [6],
                "candidate_alerts": [0],
                "alert_delta": [-6],
            }
        ),
    }

    summary, reason, report = write_report(
        results,
        tmp_path / "summary.csv",
        tmp_path / "reason.csv",
        tmp_path / "report.md",
    )

    assert pd.read_csv(summary).shape[0] == 2
    assert pd.read_csv(reason).iloc[0]["alert_delta"] == -6
    text = report.read_text(encoding="utf-8")
    assert "Rule Config Compare" in text
    assert "co2_high;nh3_high" in text
