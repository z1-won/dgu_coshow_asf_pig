import pandas as pd

from pigproject.multimodal_behavior_baseline import (
    build_window_features,
    group_split,
    train_and_evaluate,
)


def _write_long_csv(path, rows_per_window=4):
    """Two animals, two windows each, two labels -- lying windows have near-zero
    AZ variance (resting), walking windows have swinging AZ (movement)."""
    records = []
    specs = [
        ("1", 1, "lying", [1.0, 1.0, 1.0, 1.0]),
        ("1", 2, "walking", [1.0, 5.0, 1.0, 5.0]),
        ("2", 1, "lying", [1.0, 1.1, 0.9, 1.0]),
        ("2", 2, "walking", [1.0, 6.0, 1.0, 6.0]),
    ]
    for animal_id, janela, label, az_values in specs:
        for i in range(rows_per_window):
            records.append(
                {
                    "DataHora_ms": f"row{i}",
                    "instante_tempo": i,
                    "AX": 0.5,
                    "AY": 0.2,
                    "AZ": az_values[i % len(az_values)],
                    "ID": animal_id,
                    "atividade": label,
                    "janela": janela,
                    "label_artigo": label,
                }
            )
    pd.DataFrame(records).to_csv(path, index=False)


def test_build_window_features_aggregates_one_row_per_window(tmp_path):
    csv_path = tmp_path / "accel.csv"
    _write_long_csv(csv_path)

    features = build_window_features(csv_path)

    assert len(features) == 4  # 2 animals x 2 windows
    assert set(features["label"]) == {"lying", "walking"}
    assert all(isinstance(v, str) for v in features["ID"])  # kept as string, not coerced to int
    walking = features[features["label"] == "walking"]
    lying = features[features["label"] == "lying"]
    # walking windows swing AZ between 1 and 5/6, so std must exceed lying's near-zero std
    assert walking["az_std"].min() > lying["az_std"].max()


def test_group_split_keeps_test_ids_out_of_train(tmp_path):
    csv_path = tmp_path / "accel.csv"
    _write_long_csv(csv_path)
    features = build_window_features(csv_path)

    train, test = group_split(features, test_ids=["2"])

    assert set(train["ID"]) == {"1"}
    assert set(test["ID"]) == {"2"}
    assert len(train) + len(test) == len(features)


def test_train_and_evaluate_separates_obviously_different_classes(tmp_path):
    csv_path = tmp_path / "accel.csv"
    _write_long_csv(csv_path, rows_per_window=20)
    features = build_window_features(csv_path)
    train, test = group_split(features, test_ids=["2"])

    _, pred, report_dict, cm, macro_f1 = train_and_evaluate(train, test)

    assert len(pred) == len(test)
    assert macro_f1 == 1.0  # lying vs. walking AZ patterns are trivially separable
    assert "lying" in report_dict and "walking" in report_dict
