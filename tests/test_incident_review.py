import pandas as pd

import pytest

from pigproject.incident_review import (
    append_summary_history,
    apply_dashboard_reviews,
    apply_single_review,
    build_review_log_template,
    load_or_bootstrap_review_log,
    merge_incident_queue,
    summarize_review_log,
    write_report,
    write_review_log,
)


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


def test_merge_incident_queue_keeps_prior_review_state():
    old_log = build_review_log_template(_incident_queue())
    old_log.loc[0, "review_status"] = "confirmed"
    old_log.loc[0, "confirmed"] = True
    old_log.loc[0, "operator_note"] = "체온 상승 확인, 격리 완료"

    # simulate a fresh queue export where disease-0001 is still open but a new incident showed up
    new_queue = _incident_queue()
    new_row = new_queue.iloc[[0]].copy()
    new_row["incident_id"] = "disease-0002"
    new_row["incident_start_datetime"] = pd.Timestamp("2023-02-01")
    new_queue = pd.concat([new_queue, new_row], ignore_index=True)

    merged = merge_incident_queue(old_log, new_queue)

    assert len(merged) == 4
    reviewed = merged.set_index("incident_id").loc["disease-0001"]
    assert reviewed["review_status"] == "confirmed"
    assert reviewed["operator_note"] == "체온 상승 확인, 격리 완료"
    newly_added = merged.set_index("incident_id").loc["disease-0002"]
    assert newly_added["review_status"] == "pending"


def test_merge_incident_queue_carries_over_incidents_dropped_from_queue():
    old_log = build_review_log_template(_incident_queue())
    old_log.loc[0, "review_status"] = "confirmed"
    old_log.loc[0, "confirmed"] = True

    # new queue no longer includes disease-0001 (e.g. it rotated out of the active queue)
    new_queue = _incident_queue().iloc[1:].reset_index(drop=True)

    merged = merge_incident_queue(old_log, new_queue)

    assert "disease-0001" in merged["incident_id"].tolist()
    carried = merged.set_index("incident_id").loc["disease-0001"]
    assert carried["review_status"] == "confirmed"


def test_apply_dashboard_reviews_sets_confirmed_and_dismissed():
    review_log = build_review_log_template(_incident_queue())
    dashboard_export = pd.DataFrame(
        {
            "incident_id": ["disease-0001", "management-0001", "unknown-9999"],
            "decision": ["confirmed", "dismissed", "confirmed"],
            "resolved_at": ["2023-01-05T00:00:00Z", "2023-01-05T00:00:00Z", "2023-01-05T00:00:00Z"],
        }
    )

    updated = apply_dashboard_reviews(review_log, dashboard_export)
    by_id = updated.set_index("incident_id")

    assert by_id.loc["disease-0001", "review_status"] == "confirmed"
    assert bool(by_id.loc["disease-0001", "confirmed"]) is True
    assert by_id.loc["management-0001", "review_status"] == "false_alarm"
    assert bool(by_id.loc["management-0001", "false_alarm"]) is True
    # incident not in the queue's review log is silently skipped, not raised
    assert "unknown-9999" not in by_id.index
    # untouched incident stays pending
    assert by_id.loc["environment-0001", "review_status"] == "pending"


def test_apply_dashboard_reviews_survives_csv_roundtrip(tmp_path):
    # Regression test: an all-empty confirmed/false_alarm column comes back from
    # pd.read_csv as float64 NaN (not the object dtype an in-memory pd.NA column
    # gets), and pandas 3 raises LossySetitemError on `.loc[i, col] = True` against
    # a float64 column. apply_dashboard_reviews must handle the CSV-roundtripped
    # dtype, not just the freshly-built-in-memory one.
    review_log = build_review_log_template(_incident_queue())
    csv_path = tmp_path / "incident_review_log.csv"
    write_review_log(review_log, csv_path)
    reloaded = pd.read_csv(csv_path)

    dashboard_export = pd.DataFrame(
        {
            "incident_id": ["disease-0001"],
            "decision": ["confirmed"],
            "resolved_at": ["2026-08-30T21:00:00Z"],
        }
    )

    updated = apply_dashboard_reviews(reloaded, dashboard_export)

    assert bool(updated.set_index("incident_id").loc["disease-0001", "confirmed"]) is True


def test_append_summary_history_accumulates_across_calls(tmp_path):
    history_path = tmp_path / "incident_review_summary_history.csv"
    review_log = build_review_log_template(_incident_queue())
    summary_1 = summarize_review_log(review_log)

    first = append_summary_history(summary_1, history_path)
    assert len(first) == len(summary_1)
    assert "snapshot_at" in first.columns

    review_log.loc[0, "review_status"] = "confirmed"
    review_log.loc[0, "confirmed"] = True
    summary_2 = summarize_review_log(review_log)
    second = append_summary_history(summary_2, history_path)

    # second call adds new rows on top of the first snapshot rather than replacing it
    assert len(second) == len(summary_1) + len(summary_2)
    on_disk = pd.read_csv(history_path)
    assert len(on_disk) == len(second)


def test_apply_single_review_confirms_one_incident():
    review_log = build_review_log_template(_incident_queue())

    updated = apply_single_review(review_log, "disease-0001", "confirmed", reviewed_by="operator1")

    row = updated.set_index("incident_id").loc["disease-0001"]
    assert row["review_status"] == "confirmed"
    assert bool(row["confirmed"]) is True
    assert row["reviewed_by"] == "operator1"
    assert row["resolved_at"]  # timestamp was set
    # untouched incidents remain pending
    assert updated.set_index("incident_id").loc["management-0001", "review_status"] == "pending"


def test_apply_single_review_survives_csv_roundtrip(tmp_path):
    review_log = build_review_log_template(_incident_queue())
    csv_path = tmp_path / "incident_review_log.csv"
    write_review_log(review_log, csv_path)
    reloaded = pd.read_csv(csv_path)

    updated = apply_single_review(reloaded, "disease-0001", "dismissed")

    assert bool(updated.set_index("incident_id").loc["disease-0001", "false_alarm"]) is True


def test_apply_single_review_raises_for_unknown_incident():
    review_log = build_review_log_template(_incident_queue())

    with pytest.raises(KeyError):
        apply_single_review(review_log, "does-not-exist", "confirmed")


def test_load_or_bootstrap_review_log_creates_then_reuses(tmp_path):
    incident_csv = tmp_path / "incident_queue.csv"
    _incident_queue().to_csv(incident_csv, index=False)
    output_csv = tmp_path / "incident_review_log.csv"

    first = load_or_bootstrap_review_log(output_csv, incident_csv)
    assert len(first) == 3
    assert (first["review_status"] == "pending").all()

    # simulate a review happening and being persisted
    reviewed = apply_single_review(first, "disease-0001", "confirmed")
    write_review_log(reviewed, output_csv)

    second = load_or_bootstrap_review_log(output_csv, incident_csv)
    assert second.set_index("incident_id").loc["disease-0001", "review_status"] == "confirmed"


def test_write_review_log_and_report(tmp_path):
    review_log = build_review_log_template(_incident_queue())
    summary = summarize_review_log(review_log)
    csv_path = write_review_log(review_log, tmp_path / "incident_review_log_template.csv")
    report = write_report(review_log, summary, tmp_path / "incident_review_report.md")

    assert pd.read_csv(csv_path).shape[0] == 3
    text = report.read_text(encoding="utf-8")
    assert "Incident Review Log" in text
    assert "Pending Incidents" in text
