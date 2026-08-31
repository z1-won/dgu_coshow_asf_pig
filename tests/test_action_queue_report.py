import pandas as pd

from pigproject.action_queue_report import (
    build_action_queue,
    build_incident_queue,
    write_action_queues,
    write_incident_queue,
    write_report,
)


def _alerts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track": ["bioenergy", "bioenergy", "bioenergy"],
            "source_dataset": ["71408", "71763", "71408"],
            "chamber_id": ["bioenergy:71408:4", "bioenergy:71763:1", "bioenergy:71408:1"],
            "start_datetime": pd.to_datetime(["2023-01-01 00:00", "2023-01-02 00:00", "2023-01-03 00:00"]),
            "end_datetime": pd.to_datetime(["2023-01-01 04:00", "2023-01-02 04:00", "2023-01-03 04:00"]),
            "track_score": [1.4, 0.2, 0.3],
            "management_score": [0.0, 0.6, 0.0],
            "environment_score": [0.3, 0.0, 0.9],
            "tier": ["medium", "normal", "normal"],
            "alert_category": ["disease,environment", "management", "environment"],
            "environment_temp_policy": ["balanced", "normal", "high_confidence"],
            "environment_temp_label": ["균형", "정상 범위", "고확신"],
            "environment_temp_action": ["환경 이상 기본 기준 후보", "온도 기준 이상 없음", "CCTV/현장 확인 우선순위"],
            "reason": [
                "rule: disease: rectal_temp_high | environment: co2_high",
                "rule: management: feed_drop",
                "rule: environment: co2_high,nh3_high",
            ],
        }
    )


def test_build_action_queue_expands_categories_and_actions():
    queue = build_action_queue(_alerts())

    assert len(queue) == 4
    assert queue["queue"].value_counts().to_dict() == {"environment": 2, "disease": 1, "management": 1}
    assert "수의사" in queue[queue["queue"] == "disease"]["recommended_action"].iloc[0]
    assert "급이기" in queue[queue["queue"] == "management"]["recommended_action"].iloc[0]
    assert "환기량" in queue[queue["reason"].str.contains("nh3_high")]["recommended_action"].iloc[0]
    assert set(["environment_temp_policy", "environment_temp_label", "environment_temp_action"]).issubset(queue.columns)


def test_build_incident_queue_groups_adjacent_windows():
    alerts = pd.concat(
        [
            _alerts(),
            pd.DataFrame(
                {
                    "track": ["bioenergy", "bioenergy"],
                    "source_dataset": ["71408", "71408"],
                    "chamber_id": ["bioenergy:71408:1", "bioenergy:71408:1"],
                    "start_datetime": pd.to_datetime(["2023-01-03 02:00", "2023-01-07 00:00"]),
                    "end_datetime": pd.to_datetime(["2023-01-03 06:00", "2023-01-07 04:00"]),
                    "track_score": [0.4, 0.5],
                    "management_score": [0.0, 0.0],
                    "environment_score": [0.9, 0.9],
                    "tier": ["normal", "normal"],
                    "alert_category": ["environment", "environment"],
                    "reason": ["rule: environment: co2_high,nh3_high", "rule: environment: co2_high,nh3_high"],
                }
            ),
        ],
        ignore_index=True,
    )
    queue = build_action_queue(alerts)
    incidents = build_incident_queue(queue, max_gap_hours=24)

    environment_incidents = incidents[
        (incidents["queue"] == "environment") & (incidents["chamber_id"] == "bioenergy:71408:1")
    ].sort_values("incident_start_datetime")
    assert environment_incidents["window_count"].tolist() == [2, 1]
    assert environment_incidents.iloc[0]["environment_temp_label"] == "고확신"
    assert incidents["incident_id"].str.contains("-").all()


def test_write_action_queues_and_report(tmp_path):
    queue = build_action_queue(_alerts())
    incidents = build_incident_queue(queue)
    paths = write_action_queues(queue, tmp_path)
    incident_path = write_incident_queue(incidents, tmp_path / "incident_queue.csv")
    report = write_report(queue, tmp_path / "action_queue_report.md", incident_queue=incidents)

    assert set(paths) == {"combined", "disease", "management", "environment"}
    assert pd.read_csv(paths["combined"]).shape[0] == 4
    assert pd.read_csv(paths["management"]).shape[0] == 1
    assert pd.read_csv(incident_path).shape[0] == 4
    report_text = report.read_text(encoding="utf-8")
    assert "Incident Queue" in report_text
    assert "Management Queue" in report_text
    assert "rectal_temp_high ; environment: co2_high" in report_text
