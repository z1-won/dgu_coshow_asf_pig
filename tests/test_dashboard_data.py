import pandas as pd

from pigproject.dashboard_data import (
    building_label,
    chamber_room,
    date_only,
    load_chambers,
    load_incidents,
    reason_parts,
    track_label,
)


def test_building_label_maps_bioenergy_sources_and_activity_622():
    assert building_label("bioenergy", "71408") == "1동"
    assert building_label("bioenergy", "71763") == "2동"
    assert building_label("activity_622", "622") == "3동"
    assert building_label("other", "99") == "99"  # unknown track: bare source_dataset, no "동" suffix (matches the .mjs generator)


def test_chamber_room_parses_bioenergy_and_activity_ids():
    assert chamber_room("bioenergy:71408:4") == "4번 돈방"
    assert chamber_room("activity622:facility3:pen7") == "3구역 7번방"
    assert chamber_room("unknown:id") == "unknown:id"


def test_track_label_translates_known_tracks_and_passes_through_unknown():
    assert track_label("bioenergy") == "체온·환경 센서"
    assert track_label("activity_622") == "카메라 행동분석"
    assert track_label("mystery_track") == "mystery_track"


def test_reason_parts_extracts_known_tokens_without_duplicates():
    assert reason_parts("rule: disease: rectal_temp_high | environment: co2_high") == ["체온 상승", "이산화탄소 농도 상승"]
    assert reason_parts("rectal_temp_high, rectal_temp_high") == ["체온 상승"]


def test_reason_parts_falls_back_to_splitting_unknown_reason():
    assert reason_parts("rule: some_custom_rule | another_rule") == ["some_custom_rule", "another_rule"]


def test_date_only_strips_time_component():
    assert date_only("2022-11-23 13:28:00") == "2022-11-23"
    assert date_only("") == ""
    assert date_only(None) == ""


def test_load_chambers_adds_no_data_room_when_71408_3_is_missing(tmp_path):
    csv_path = tmp_path / "final_chamber_summary.csv"
    pd.DataFrame(
        [
            {
                "chamber_id": "bioenergy:71408:4",
                "track": "bioenergy",
                "source_dataset": "71408",
                "windows": 10,
                "mean_score": 1.2506,
                "max_score": 1.3705,
                "chamber_tier": "medium",
                "low_confidence": "False",
            },
        ]
    ).to_csv(csv_path, index=False)

    result = load_chambers(csv_path)

    assert len(result["chambers"]) == 1
    assert result["chambers"][0]["buildingLabel"] == "1동"
    assert result["chambers"][0]["room"] == "4번 돈방"
    assert len(result["noDataRooms"]) == 1
    assert result["noDataRooms"][0]["id"] == "bioenergy:71408:3-nodata"
    assert result["totalRooms"] == 2
    assert result["buildings"] == ["1동"]


def test_load_chambers_omits_no_data_room_when_71408_3_is_present(tmp_path):
    csv_path = tmp_path / "final_chamber_summary.csv"
    pd.DataFrame(
        [
            {
                "chamber_id": "bioenergy:71408:3",
                "track": "bioenergy",
                "source_dataset": "71408",
                "windows": 24,
                "mean_score": 0.1,
                "max_score": 0.2,
                "chamber_tier": "normal",
                "low_confidence": "False",
            },
        ]
    ).to_csv(csv_path, index=False)

    result = load_chambers(csv_path)

    assert result["noDataRooms"] == []
    assert result["totalRooms"] == 1


def test_load_incidents_picks_score_by_queue_and_translates_reason(tmp_path):
    csv_path = tmp_path / "incident_queue.csv"
    pd.DataFrame(
        [
            {
                "incident_id": "disease-0001",
                "chamber_id": "bioenergy:71408:4",
                "queue": "disease",
                "incident_start_datetime": "2022-11-23 13:28:00",
                "incident_end_datetime": "2022-12-05 13:41:00",
                "window_count": 10,
                "max_track_score": 1.37053684241568,
                "max_management_score": 0.0,
                "max_environment_score": 0.3,
                "reason": "rule: disease: rectal_temp_high | environment: co2_high",
                "recommended_action": "체온 상승 개체 확인",
            }
        ]
    ).to_csv(csv_path, index=False)

    incidents = load_incidents(csv_path)

    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["id"] == "disease-0001"
    assert incident["start"] == "2022-11-23"
    assert incident["end"] == "2022-12-05"
    assert incident["score"] == 1.3705  # picked max_track_score (queue=disease), not the environment score
    assert incident["reasonParts"] == ["체온 상승", "이산화탄소 농도 상승"]
