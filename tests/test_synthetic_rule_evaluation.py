import pandas as pd

from pigproject.synthetic_rule_evaluation import summarize_file


def test_summarize_file_computes_recall_by_dataset_and_rule(tmp_path):
    path = tmp_path / "summary.csv"
    pd.DataFrame(
        {
            "event_id": ["e1", "e2"],
            "event_type": ["fever", "feed_drop"],
            "expected_rule": ["rectal_temp_high", "feed_drop"],
            "lead_alert_count": [1, 0],
            "caught_within_24h": [True, False],
            "caught_within_48h": [True, False],
            "caught_within_72h": [True, False],
        }
    ).to_csv(path, index=False)

    summary, by_rule = summarize_file("mixed", path)

    assert summary["dataset"] == "mixed"
    assert summary["events"] == 2
    assert summary["lead_matched_events"] == 1
    assert summary["recall_24h"] == 0.5
    assert set(by_rule["expected_rule"]) == {"rectal_temp_high", "feed_drop"}
