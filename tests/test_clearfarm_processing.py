import pandas as pd

from pigproject.clearfarm_processing import build_feeding_hour, build_health_day, normalize_pen_value, parse_clearfarm_date, parse_exp1_ivog_station


def test_parse_clearfarm_date_handles_iso_and_yyyymmdd():
    parsed = parse_clearfarm_date(pd.Series(["2022-05-13", 20220517, "17/05/2022"]))
    assert parsed.dt.strftime("%Y-%m-%d").tolist() == ["2022-05-13", "2022-05-17", "2022-05-17"]


def test_normalize_pen_value_adds_experiment_suffix():
    assert normalize_pen_value("A2", 3) == "A2.3"
    assert normalize_pen_value("A2.3", 3) == "A2.3"
    assert normalize_pen_value("10", 1) == "10"


def test_parse_exp1_ivog_station_handles_f_labels():
    assert parse_exp1_ivog_station("F2") == 2.0
    assert parse_exp1_ivog_station("F10") == 10.0


def test_build_health_day_maps_exp1_ivog_via_station_map(tmp_path):
    exp_dir = tmp_path / "Exp1 (dec2020-feb2021)"
    exp_dir.mkdir()
    health = pd.DataFrame(
        [
            {"experiment": 1, "date": 20201208, "pen": 1, "ivog": "F10", "pig": 1001, "cough": 1, "diar": 0},
            {"experiment": 1, "date": 20201208, "pen": 1, "ivog": "F10", "pig": 1002, "cough": 0, "diar": 1},
        ]
    )
    with pd.ExcelWriter(exp_dir / "Exp1 - On-farm observations.xlsx") as writer:
        health.to_excel(writer, sheet_name="Raw data", index=False)

    station_map = pd.DataFrame([{"experiment": 1, "station": 10, "pen_id": "F3.1", "registered_pigs": 11}])
    result = build_health_day(tmp_path, station_map)
    row = result.iloc[0]

    assert row["pen_id"] == "F3.1"
    assert row["health_observation_rows"] == 2
    assert row["cough_sum"] == 1
    assert row["diar_sum"] == 1


def test_build_feeding_hour_sums_valid_visits_per_pen_hour(tmp_path):
    exp_dir = tmp_path / "Exp1 (dec2020-feb2021)"
    exp_dir.mkdir()
    feeding = pd.DataFrame(
        [
            {"date": "2020-12-04", "tattoo": "AB12", "pig": 1, "station": 10, "intake": 0.05, "hour": 8, "duration": 20, "rate": 0.15},
            {"date": "2020-12-04", "tattoo": "AB12", "pig": 1, "station": 10, "intake": 0.03, "hour": 8, "duration": 15, "rate": 0.12},
            {"date": "2020-12-04", "tattoo": "AB12", "pig": 1, "station": 10, "intake": 0.10, "hour": 9, "duration": 30, "rate": 0.20},
            {"date": "2020-12-04", "tattoo": "FILLING", "pig": 0, "station": 10, "intake": 0.02, "hour": 8, "duration": 5, "rate": 0.02},
        ]
    )
    feeding.to_csv(exp_dir / "Exp1 - Feeding data.csv", index=False)

    station_map = pd.DataFrame([{"experiment": 1, "station": 10, "pen_id": "A2.1", "registered_pigs": 11}])
    result = build_feeding_hour(tmp_path, station_map)

    hour8 = result[result["datetime"] == pd.Timestamp("2020-12-04 08:00:00")].iloc[0]
    hour9 = result[result["datetime"] == pd.Timestamp("2020-12-04 09:00:00")].iloc[0]
    assert hour8["feed_intake_kg"] == 0.08  # FILLING row excluded
    assert hour8["feed_visits"] == 2
    assert hour9["feed_intake_kg"] == 0.10
