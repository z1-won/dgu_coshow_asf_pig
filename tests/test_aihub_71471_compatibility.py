import pandas as pd

from pigproject.aihub_71471_compatibility import (
    build_distribution_comparison,
    build_feature_compatibility,
    decide_compatibility,
)


def test_feature_compatibility_maps_71471_to_622_names() -> None:
    behavior_71471 = pd.DataFrame(
        {
            "annotation_count": [10],
            "lying_ratio": [0.7],
            "estrus_ratio": [1.0],
        }
    )
    activity_622 = pd.DataFrame(
        {
            "point_annotation_count": [12],
            "lying_ratio": [0.6],
        }
    )

    table = build_feature_compatibility(behavior_71471, activity_622)

    annotation_row = table[table["feature_71471"] == "annotation_count"].iloc[0]
    estrus_row = table[table["feature_71471"] == "estrus_ratio"].iloc[0]
    assert annotation_row["feature_622"] == "point_annotation_count"
    assert bool(annotation_row["compatible"]) is True
    assert bool(estrus_row["compatible"]) is False


def test_distribution_comparison_uses_mapped_columns() -> None:
    behavior_71471 = pd.DataFrame({"annotation_count": [10, 20], "lying_ratio": [0.2, 0.4]})
    activity_622 = pd.DataFrame({"point_annotation_count": [5, 15], "lying_ratio": [0.1, 0.3]})

    distribution = build_distribution_comparison(behavior_71471, activity_622)

    annotation_row = distribution[distribution["feature_71471"] == "annotation_count"].iloc[0]
    assert annotation_row["mean_71471"] == 15.0
    assert annotation_row["mean_622"] == 10.0


def test_decide_compatibility_marks_auxiliary_when_enough_features_match() -> None:
    table = pd.DataFrame(
        {
            "feature_71471": [f"f{i}" for i in range(12)] + ["estrus_ratio"],
            "compatible": [True] * 10 + [False] * 2 + [False],
            "available_71471": [True] * 13,
        }
    )

    decision = decide_compatibility(table)

    assert decision["decision"] == "compatible_as_auxiliary_behavior_track"
    assert decision["comparable_features"] == 10
