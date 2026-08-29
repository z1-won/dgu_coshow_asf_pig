import numpy as np
import pandas as pd

from pigproject.behavior_heat_tolerance import (
    BEHAVIOR_FEATURES,
    FEATURE_COLUMNS,
    fit_transform_global_tn_scaler,
    load_source,
    resample_to_10min,
    resolve_feature_columns,
    split_tn_train_val,
)


def test_resample_to_10min_builds_posture_temperature_features(tmp_path):
    path = tmp_path / "behavior.csv"
    rows = []
    for idx in range(30):
        rows.append(
            {
                "date": pd.Timestamp("2026-01-01 00:00") + pd.Timedelta(seconds=20 * idx),
                "anim": 1,
                "posture": "Standing" if idx < 15 else "Sternal",
                "muscle_temp": 38.0 + idx * 0.01,
                "ambient_temp": 22.0,
                "condition": "TN",
                "adg": 100.0,
                "feed_efficiency": 0.2,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)

    source = load_source(path)
    resampled = resample_to_10min(source)

    assert len(resampled) == 1
    assert set(FEATURE_COLUMNS).issubset(resampled.columns)
    assert resampled["posture_standing_ratio"].iloc[0] == 0.5
    assert resampled["posture_sternal_ratio"].iloc[0] == 0.5
    assert resampled["muscle_temp_mean"].iloc[0] == np.mean([38.0 + idx * 0.01 for idx in range(30)])


def test_split_tn_train_val_skips_animals_without_windows():
    rows = []
    for anim, count in [("1", 60), ("2", 8)]:
        for idx in range(count):
            rows.append(
                {
                    "anim": anim,
                    "datetime": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=10 * idx),
                    "condition": "TN",
                    **{feature: 1.0 for feature in FEATURE_COLUMNS},
                }
            )
    df = pd.DataFrame(rows)

    train_df, val_df, summary = split_tn_train_val(df, train_ratio=0.5, seq_len=5)

    assert set(train_df["anim"]) == {"1"}
    assert set(val_df["anim"]) == {"1"}
    assert summary.set_index("anim").loc["2", "status"] == "skipped_no_windows"


def test_global_tn_scaler_can_transform_hs_only_animals():
    base = {feature: 1.0 for feature in FEATURE_COLUMNS}
    train = pd.DataFrame([{**base, "anim": "tn1"}])
    val = pd.DataFrame([{**base, "anim": "tn1"}])
    hs = pd.DataFrame([{**base, "anim": "hs1"}])

    _, _, hs_scaled, scaler = fit_transform_global_tn_scaler(train, val, hs)

    assert scaler.mean_.shape[0] == len(FEATURE_COLUMNS)
    assert hs_scaled[FEATURE_COLUMNS].notna().all().all()


def test_behavior_only_profile_excludes_temperature_features():
    features = resolve_feature_columns("behavior_only")

    assert features == BEHAVIOR_FEATURES
    assert "ambient_temp_mean" not in features
    assert "muscle_temp_mean" not in features
