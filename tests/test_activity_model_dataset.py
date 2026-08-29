import pandas as pd
import pytest

from pigproject.activity_model_dataset import fit_scalers_per_pen, transform_per_pen


def _train_df() -> pd.DataFrame:
    # pen (1, 1) has a much higher baseline than pen (1, 2) -- a pooled
    # scaler would let that baseline gap dominate; a per-pen scaler should
    # center each pen on its own mean instead.
    return pd.DataFrame(
        {
            "facility_number": [1, 1, 1, 1],
            "pen_number": [1, 1, 2, 2],
            "value": [10.0, 12.0, 0.1, 0.3],
        }
    )


def test_fit_scalers_per_pen_creates_one_scaler_per_group():
    scalers = fit_scalers_per_pen(_train_df(), ["value"])

    assert set(scalers.keys()) == {(1, 1), (1, 2)}
    assert scalers[(1, 1)].mean_[0] == 11.0
    assert scalers[(1, 2)].mean_[0] == 0.2


def test_transform_per_pen_centers_each_group_independently():
    train_df = _train_df()
    scalers = fit_scalers_per_pen(train_df, ["value"])
    scaled = transform_per_pen(train_df, ["value"], scalers)

    # Each pen's own values straddle zero after scaling with its own scaler,
    # even though pen (1, 1)'s raw values are ~50x pen (1, 2)'s.
    pen1 = scaled[scaled["pen_number"] == 1]["value"]
    pen2 = scaled[scaled["pen_number"] == 2]["value"]
    assert pen1.mean() == pytest.approx(0.0)
    assert pen2.mean() == pytest.approx(0.0)
    assert set(pen1.round(4)) == {-1.0, 1.0}
    assert set(pen2.round(4)) == {-1.0, 1.0}


def test_transform_per_pen_raises_for_unseen_group():
    train_df = _train_df()
    scalers = fit_scalers_per_pen(train_df, ["value"])
    unseen = pd.DataFrame({"facility_number": [9], "pen_number": [9], "value": [1.0]})

    try:
        transform_per_pen(unseen, ["value"], scalers)
        raised = False
    except KeyError:
        raised = True
    assert raised
