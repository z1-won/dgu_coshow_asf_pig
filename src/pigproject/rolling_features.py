"""Time-based rolling features (rolling mean/std, z-score, delta) for intake/behavior columns.

Row spacing within a chamber is irregular (median ~1-3.5h gaps, but up to
multi-day gaps during collection breaks), so these use a calendar-time
rolling window ('3D') rather than a fixed row count -- a fixed-row window
would span very different real time spans depending on how dense the data
happens to be around each point. Modeled on the feature set from Lagua et
al. (rolling mean, rolling std, z-score, delta), where a 3-day water-intake
rolling mean was the single most discriminative normal/abnormal feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ROLLING_WINDOW = "3D"


def add_rolling_features(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    parts = []
    for _, group in df.groupby(["dataset_key", "chamber_number"], dropna=False):
        group = group.sort_values("datetime").set_index("datetime")
        for col in columns:
            if col not in group.columns:
                continue
            roll_mean = group[col].rolling(ROLLING_WINDOW, min_periods=1).mean()
            roll_std = group[col].rolling(ROLLING_WINDOW, min_periods=1).std()
            zscore = (group[col] - roll_mean) / roll_std.replace(0, np.nan)
            group[f"{col}_roll_mean_3d"] = roll_mean
            group[f"{col}_roll_std_3d"] = roll_std.fillna(0)
            group[f"{col}_zscore_3d"] = zscore.fillna(0)
            group[f"{col}_delta"] = group[col].diff().fillna(0)
        parts.append(group.reset_index())

    result = pd.concat(parts, ignore_index=True)
    return result.sort_values(["dataset_key", "chamber_number", "datetime"]).reset_index(drop=True)
