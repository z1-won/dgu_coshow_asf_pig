import math

import pandas as pd

from pigproject.cv_tracking_features import (
    add_track_motion,
    build_activity_compat,
    build_cv_tracking_features,
    build_frame_features,
    build_track_summary,
    load_tracking_boxes,
)


def test_load_tracking_boxes_accepts_minimum_columns(tmp_path):
    path = tmp_path / "tracks.csv"
    path.write_text("frame,track_id,x,y,w,h,conf\n0,1,0,0,10,10,0.9\n", encoding="utf-8")

    df = load_tracking_boxes(path)

    assert list(df[["frame", "track_id", "x", "y", "w", "h", "conf"]].columns) == ["frame", "track_id", "x", "y", "w", "h", "conf"]
    assert df.loc[0, "pen_id"] == "unknown_pen"


def test_add_track_motion_computes_center_distance_and_speed():
    df = pd.DataFrame(
        {
            "source_video": ["v", "v"],
            "pen_id": ["pen1", "pen1"],
            "frame": [0, 1],
            "track_id": [1, 1],
            "x": [0, 3],
            "y": [0, 4],
            "w": [10, 10],
            "h": [10, 10],
            "conf": [0.9, 0.9],
            "fps": [30, 30],
            "frame_width": [100, 100],
            "frame_height": [100, 100],
            "timestamp": [pd.NaT, pd.NaT],
        }
    )

    motion = add_track_motion(df)

    assert math.isclose(motion.loc[1, "movement_px"], 5.0)
    assert math.isclose(motion.loc[1, "speed_px_per_sec"], 150.0)


def test_build_summaries_and_activity_compat():
    df = pd.DataFrame(
        {
            "source_video": ["v", "v", "v", "v"],
            "pen_id": ["pen1", "pen1", "pen1", "pen1"],
            "frame": [0, 1, 0, 1],
            "track_id": [1, 1, 2, 2],
            "x": [0, 10, 50, 50],
            "y": [0, 0, 50, 50],
            "w": [10, 10, 10, 10],
            "h": [10, 10, 10, 10],
            "conf": [0.9, 0.9, 0.8, 0.8],
            "fps": [10, 10, 10, 10],
            "frame_width": [100, 100, 100, 100],
            "frame_height": [100, 100, 100, 100],
            "timestamp": [pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        }
    )
    motion = add_track_motion(df)
    track_summary = build_track_summary(motion)
    frame_features = build_frame_features(motion)
    compat = build_activity_compat(frame_features, facility_number=3, chamber_number=4)

    assert len(track_summary) == 2
    assert len(frame_features) == 2
    assert compat.loc[0, "facility_number"] == 3
    assert "center_movement" in compat.columns


def test_build_cv_tracking_features_writes_outputs(tmp_path):
    path = tmp_path / "tracks.csv"
    path.write_text(
        "source_video,pen_id,frame,track_id,x,y,w,h,conf,fps,frame_width,frame_height\n"
        "v,pen1,0,1,0,0,10,10,0.9,10,100,100\n"
        "v,pen1,1,1,3,4,10,10,0.9,10,100,100\n",
        encoding="utf-8",
    )

    build_cv_tracking_features(path, tmp_path / "artifacts", tmp_path / "frame.csv", tmp_path / "activity.csv")

    assert (tmp_path / "artifacts" / "cv_tracking_track_summary.csv").exists()
    assert (tmp_path / "frame.csv").exists()
    assert (tmp_path / "activity.csv").exists()
