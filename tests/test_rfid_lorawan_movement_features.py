import pandas as pd

from pigproject.rfid_lorawan_movement_features import (
    add_activity_drop_features,
    build_pig_day,
    build_pig_hour,
    load_movement,
)


def test_load_movement_strips_columns_and_parses_hour(tmp_path):
    path = tmp_path / "movement.csv"
    path.write_text("pid_id ;Day_s;distance;Hour\nET00008 ;8;4.7;00:00:00\nET00008 ;8;;01:00:00\n", encoding="utf-8-sig")

    df = load_movement(path)

    assert list(df.columns) == ["pig_id", "day", "hour", "distance"]
    assert len(df) == 1  # the row with a missing distance is dropped
    assert df.iloc[0]["hour"] == 0


def test_build_pig_hour_sums_repeated_readings_in_the_same_hour():
    df = pd.DataFrame(
        [
            {"pig_id": "A", "day": 1, "hour": 0, "distance": 3.0},
            {"pig_id": "A", "day": 1, "hour": 0, "distance": 2.0},
            {"pig_id": "A", "day": 1, "hour": 1, "distance": 5.0},
        ]
    )

    pig_hour = build_pig_hour(df)

    row = pig_hour[(pig_hour["hour"] == 0)].iloc[0]
    assert row["distance_sum_hour"] == 5.0
    assert row["reading_count_hour"] == 2


def test_build_pig_day_flags_low_data_day_and_computes_night_ratio():
    rows = []
    for hour in range(24):
        rows.append({"pig_id": "A", "day": 1, "hour": hour, "distance_sum_hour": 1.0, "reading_count_hour": 1})
    pig_hour_full = pd.DataFrame(rows)
    pig_hour_sparse = pd.DataFrame(rows[:5])  # only 5 hours observed
    pig_hour_sparse["day"] = 2

    pig_day = build_pig_day(pd.concat([pig_hour_full, pig_hour_sparse], ignore_index=True))

    day1 = pig_day[pig_day["day"] == 1].iloc[0]
    day2 = pig_day[pig_day["day"] == 2].iloc[0]
    assert day1["hours_observed"] == 24
    assert day1["low_data_day"] == False  # noqa: E712 (numpy bool_, not python bool)
    assert day2["low_data_day"] == True  # noqa: E712
    assert day1["distance_sum_day"] == 24.0


def test_add_activity_drop_features_computes_pct_change_and_zscore():
    pig_day = pd.DataFrame(
        [
            {"pig_id": "A", "day": 1, "distance_sum_day": 100.0},
            {"pig_id": "A", "day": 2, "distance_sum_day": 50.0},
            {"pig_id": "A", "day": 3, "distance_sum_day": 100.0},
        ]
    )

    out = add_activity_drop_features(pig_day)

    assert pd.isna(out.iloc[0]["activity_drop_pct_1d"])
    assert out.iloc[1]["activity_drop_pct_1d"] == -0.5
    assert out["activity_drop_zscore"].notna().all()
