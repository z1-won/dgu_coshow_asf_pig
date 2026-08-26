"""Data loading utilities for AI Hub smart pig farm records."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


FIELD_ALIASES = {
    "chamber_number": [
        ("ImageInfo", "chamber-number"),
        ("ImageInfo", "chamber_number"),
        ("chamber-number",),
        ("chamber_number",),
    ],
    "date": [("ImageInfo", "date"), ("date",)],
    "time": [("ImageInfo", "time"), ("time",)],
    "timestamp": [("ImageInfo", "timestamp"), ("timestamp",)],
    "distance": [
        ("annotations", "distance"),
        ("Annotations", "distance"),
        ("distance",),
    ],
    "T": [("SensorData", "T"), ("SensorData", "temperature"), ("T",)],
    "RH": [("SensorData", "RH"), ("SensorData", "humidity"), ("RH",)],
    "CO2": [("SensorData", "CO2"), ("CO2",)],
    "NH3": [("SensorData", "NH3"), ("NH3",)],
    "breath_rate": [
        ("breath-rate",),
        ("breath_rate",),
        ("BreathRate", "breath-rate"),
        ("BreathRate", "breath_rate"),
    ],
    "rectal_temperature": [
        ("TemperatureData", "rectal-temperature"),
        ("TemperatureData", "rectal_temperature"),
        ("rectal-temperature",),
    ],
    "back_temperature": [
        ("TemperatureData", "back-temperature"),
        ("TemperatureData", "back_temperature"),
        ("back-temperature",),
    ],
    "neck_temperature": [
        ("TemperatureData", "neck-temperature"),
        ("TemperatureData", "neck_temperature"),
        ("neck-temperature",),
    ],
    "head_temperature": [
        ("TemperatureData", "head-temperature"),
        ("TemperatureData", "head_temperature"),
        ("head-temperature",),
    ],
    "ventilation_rate": [
        ("FeedingAndManagementData", "ventilation-rate"),
        ("FeedingAndManagementData", "ventilation_rate"),
        ("ventilation-rate",),
    ],
    "feedstuff_volume": [
        ("FeedingAndManagementData", "feedstuff_volume"),
        ("FeedingAndManagementData", "feedstuff-volume"),
        ("feedstuff_volume",),
    ],
    "watersupply": [
        ("FeedingAndManagementData", "watersupply"),
        ("water_supply",),
        ("watersupply",),
    ],
}


def dig(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return np.nan
        current = current[key]
    return current


def first_value(data: dict[str, Any], aliases: Iterable[tuple[str, ...]]) -> Any:
    for path in aliases:
        value = dig(data, path)
        if not (isinstance(value, float) and np.isnan(value)):
            return value
    return np.nan


def iter_json_paths(json_dir: str | Path, max_files: int | None = None) -> list[str]:
    paths = sorted(glob.glob(str(Path(json_dir) / "**" / "*.json"), recursive=True))
    return paths if max_files is None else paths[:max_files]


def load_json_records(json_dir: str | Path, max_files: int | None = None) -> pd.DataFrame:
    records = []
    for path in iter_json_paths(json_dir, max_files=max_files):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        row = {name: first_value(data, aliases) for name, aliases in FIELD_ALIASES.items()}
        row["source_file"] = path
        records.append(row)

    if not records:
        raise FileNotFoundError(f"No JSON files found under: {json_dir}")

    return pd.DataFrame(records)
