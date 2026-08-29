import pytest

from pigproject.rule_candidate_config import build_candidate_config, parse_overrides, write_candidate_outputs


def _config() -> dict:
    return {
        "combine": "OR",
        "rules": [
            {
                "id": "co2_high",
                "feature": "CO2_mean",
                "op": ">=",
                "threshold": 1000,
                "category": "environment",
                "note": "base note",
            },
            {
                "id": "rectal_temp_high",
                "feature": "rectal_temperature_mean_corrected",
                "op": ">=",
                "threshold": 39.5,
                "category": "disease",
            },
        ],
    }


def test_parse_overrides_defaults_and_custom_values():
    assert parse_overrides("") == {"co2_high": 1100}
    assert parse_overrides("co2_high=1200,nh3_high=12") == {"co2_high": 1200.0, "nh3_high": 12.0}


def test_build_candidate_config_updates_copy_and_records_change():
    base = _config()
    candidate, changes = build_candidate_config(base, {"co2_high": 1100})

    co2 = [rule for rule in candidate["rules"] if rule["id"] == "co2_high"][0]
    assert co2["threshold"] == 1100
    assert "threshold 1000 -> 1100" in co2["note"]
    assert base["rules"][0]["threshold"] == 1000
    assert changes.iloc[0]["rule_id"] == "co2_high"
    assert changes.iloc[0]["old_threshold"] == 1000
    assert changes.iloc[0]["candidate_threshold"] == 1100


def test_build_candidate_config_rejects_unknown_rule():
    with pytest.raises(ValueError, match="Unknown rule ids"):
        build_candidate_config(_config(), {"missing_rule": 1})


def test_write_candidate_outputs(tmp_path):
    candidate, changes = build_candidate_config(_config(), {"co2_high": 1100})
    config_path, changes_path, report_path = write_candidate_outputs(
        candidate,
        changes,
        tmp_path / "candidate.json",
        tmp_path / "changes.csv",
        tmp_path / "report.md",
    )

    assert config_path.exists()
    assert changes_path.exists()
    assert "Candidate Rule Config" in report_path.read_text(encoding="utf-8")
