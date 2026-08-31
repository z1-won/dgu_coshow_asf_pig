from pathlib import Path

import pandas as pd

from pigproject.sowell_lead_time import (
    add_daily_scores,
    add_event_mapping,
    build_event_detection_frame,
    summarize_detection,
)


def test_add_event_mapping_marks_targets_and_controls() -> None:
    events = pd.DataFrame(
        {
            "ID_event": ["H", "C"],
            "ID_group": ["B05", "B05"],
            "Kind_event": ["hot_thermic_conditions", "control_week_hot_thermic_conditions"],
        }
    )

    mapped = add_event_mapping(events)

    assert mapped.loc[0, "project_category"] == "environment_heat"
    assert mapped.loc[0, "include_in_recall"] is True or bool(mapped.loc[0, "include_in_recall"])
    assert mapped.loc[1, "event_role"] == "control"
    assert not bool(mapped.loc[1, "include_in_recall"])


def test_build_event_detection_frame_separates_pre_and_during_hits() -> None:
    events = pd.DataFrame(
        {
            "ID_event": ["HT"],
            "ID_group": ["B05"],
            "Kind_event": ["hot_thermic_conditions"],
            "begin_dt": ["2021-02-15 12:00:00"],
            "end_dt": ["2021-02-18 12:00:00"],
        }
    )
    daily = pd.DataFrame(
        {
            "ID_group": ["B05"] * 6,
            "date": pd.to_datetime(["2021-02-12", "2021-02-13", "2021-02-14", "2021-02-15", "2021-02-16", "2021-02-17"]),
            "feed_kg_per_sow": [2.5] * 6,
            "water_l_per_sow": [5.0] * 6,
            "moving_time_mean": [4.0] * 6,
            "air_temp_mean": [20.0, 20.0, 20.0, 30.0, 31.0, 30.0],
            "air_temp_max": [21.0, 21.0, 21.0, 34.0, 35.0, 34.0],
        }
    )

    scored = add_daily_scores(daily)
    frame = build_event_detection_frame(add_event_mapping(events), scored, horizons_hours=(24, 72))
    summary = summarize_detection(frame, horizons_hours=(24, 72))

    assert bool(frame.loc[0, "during_detected"])
    assert not bool(frame.loc[0, "pre_24h_detected"])
    assert summary.loc[summary["scope"].eq("all_targets"), "during_recall"].iloc[0] == 1.0
