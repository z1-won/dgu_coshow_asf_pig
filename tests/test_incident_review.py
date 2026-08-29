import pandas as pd

from pigproject.incident_review import build_review_log_template, summarize_review_log, write_report, write_review_log


def _incident_queue() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "incident_id": ["disease-0001", "management-0001", "environment-0001"],
            "queue": ["disease", "management", "environment"],
            "priority": ["high", "watch", "high"],
            "chamber_id": ["bioenergy:71408:4", "bioenergy:71763:1", "bioenergy:71408:1"],
            "incident_start_datetime": pd.to_datetime(["2023-01-01 00:00", "2023-01-02 00:00", "2023-01-03 00:00"]),
            "incident_end_datetime": pd.to_datetime(["2023-01-02 00:00", "2023-01-02 04:00", "2023-01-04 00:00"]),
            "window_count": [10, 1, 6],
            "max_track_score": [1.3, 0.2, 0.3],
            "max_management_score": [0.0, 0.6, 0.0],
            "max_environment_score": [0.3, 0.0, 0.9],
            "reason": [
                "rule: disease: rectal_temp_high",
                "rule: management: feed_drop",
                "rule: environment: co2_high,nh3_high",
            ],
            "recommended_action": ["수의사 확인", "급이기 확인", "환기 점검"],
        }
    )


def test_build_review_log_template_adds_feedback_columns():
    review_log = build_review_log_template(_incident_queue())

    assert len(review_log) == 3
    assert review_log["review_status"].tolist() == ["pending", "pending", "pending"]
    assert "actual_cause" in review_log.columns
    assert "operator_note" in review_log.columns


def test_summarize_review_log_counts_decisions():
    review_log = build_review_log_template(_incident_queue())
    review_log.loc[0, "review_status"] = "confirmed"
    review_log.loc[0, "confirmed"] = True
    review_log.loc[1, "review_status"] = "false_alarm"
    review_log.loc[1, "false_alarm"] = True
    review_log.loc[2, "followup_required"] = True

    summary = summarize_review_log(review_log)
    all_row = summary[summary["scope"] == "all"].iloc[0]
    disease_row = summary[summary["scope"] == "disease"].iloc[0]

    assert all_row["incidents"] == 3
    assert all_row["reviewed"] == 2
    assert all_row["pending"] == 1
    assert all_row["confirmed"] == 1
    assert all_row["false_alarm"] == 1
    assert all_row["precision_estimate"] == 0.5
    assert all_row["followup_required"] == 1
    assert disease_row["precision_estimate"] == 1.0


def test_write_review_log_and_report(tmp_path):
    review_log = build_review_log_template(_incident_queue())
    summary = summarize_review_log(review_log)
    csv_path = write_review_log(review_log, tmp_path / "incident_review_log_template.csv")
    report = write_report(review_log, summary, tmp_path / "incident_review_report.md")

    assert pd.read_csv(csv_path).shape[0] == 3
    text = report.read_text(encoding="utf-8")
    assert "Incident Review Log" in text
    assert "Pending Incidents" in text
