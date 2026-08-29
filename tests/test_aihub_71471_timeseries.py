import pandas as pd

from pigproject.aihub_71471_timeseries import (
    build_71471_frame_features,
    build_71471_timeseries,
    build_frame_datetime,
    model_feature_columns,
)


def _normalized_rows() -> pd.DataFrame:
    rows = pd.DataFrame(
        {
            "split": ["training", "training", "training"],
            "farm_id": ["pigfarmA", "pigfarmA", "pigfarmA"],
            "channel": [10, 10, 10],
            "record_date_hour": ["2022071510", "2022071510", "2022071510"],
            "clip_id": ["025", "025", "025"],
            "timestamp": [0, 0, 18000],
            "member_name": ["/frame0.json", "/frame0.json", "/frame18000.json"],
            "image_file_name": [
                "pigfarmA_ch10_2022071510_025_00000.jpg",
                "pigfarmA_ch10_2022071510_025_00000.jpg",
                "pigfarmA_ch10_2022071510_025_18000.jpg",
            ],
            "annotation_id": [1, 2, 3],
            "action_name": ["lying", "standing", "eating"],
            "estrus": ["N", "Y", "Y"],
            "injection": ["Y", "Y", "N"],
            "visible_keypoints": [8, 7, 8],
            "center_x": [10.0, 20.0, 40.0],
            "center_y": [10.0, 20.0, 40.0],
            "span_x": [5.0, 6.0, 7.0],
            "span_y": [8.0, 9.0, 10.0],
        }
    )
    rows["datetime"] = build_frame_datetime(rows)
    rows["is_estrus"] = (rows["estrus"] == "Y").astype(int)
    rows["is_injected"] = (rows["injection"] == "Y").astype(int)
    return rows


def test_build_frame_datetime_uses_30fps_timestamp() -> None:
    rows = pd.DataFrame({"record_date_hour": ["2022071510"], "timestamp": [18000]})

    result = build_frame_datetime(rows)

    assert str(result.iloc[0]) == "2022-07-15 10:10:00"


def test_build_71471_frame_features_aggregates_per_image() -> None:
    frame_features = build_71471_frame_features(_normalized_rows())

    first = frame_features.iloc[0]
    assert len(frame_features) == 2
    assert first["annotation_count"] == 2
    assert first["lying_count"] == 1
    assert first["standing_count"] == 1
    assert first["estrus_ratio"] == 0.5


def test_build_71471_timeseries_excludes_label_leakage_features() -> None:
    frame_features = build_71471_frame_features(_normalized_rows())
    time_series = build_71471_timeseries(frame_features)

    assert len(time_series) == 2
    assert time_series.iloc[0]["annotation_count"] == 2
    assert time_series.iloc[0]["estrus_ratio"] == 0.5
    assert "estrus_ratio" not in model_feature_columns()
    assert "injected_ratio" not in model_feature_columns()
