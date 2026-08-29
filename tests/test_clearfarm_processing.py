import pandas as pd

from pigproject.clearfarm_processing import normalize_pen_value, parse_clearfarm_date


def test_parse_clearfarm_date_handles_iso_and_yyyymmdd():
    parsed = parse_clearfarm_date(pd.Series(["2022-05-13", 20220517, "17/05/2022"]))
    assert parsed.dt.strftime("%Y-%m-%d").tolist() == ["2022-05-13", "2022-05-17", "2022-05-17"]


def test_normalize_pen_value_adds_experiment_suffix():
    assert normalize_pen_value("A2", 3) == "A2.3"
    assert normalize_pen_value("A2.3", 3) == "A2.3"
    assert normalize_pen_value("10", 1) == "10"
