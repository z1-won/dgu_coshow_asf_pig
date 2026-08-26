"""Generate small synthetic AI Hub-like JSON files for smoke tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def make_record(chamber: str, dt: pd.Timestamp, step: int, rng: np.random.Generator) -> dict:
    daily = np.sin(2 * np.pi * (step % 144) / 144)
    activity = 18 + 5 * daily + rng.normal(0, 0.7)
    room_temp = 24 + 1.5 * daily + rng.normal(0, 0.2)

    return {
        "ImageInfo": {
            "chamber-number": chamber,
            "date": dt.strftime("%y%m%d"),
            "time": dt.strftime("%H%M"),
            "timestamp": dt.isoformat(),
        },
        "annotations": {"distance": round(float(activity), 4)},
        "SensorData": {
            "T": round(float(room_temp), 4),
            "RH": round(float(62 - 4 * daily + rng.normal(0, 0.5)), 4),
            "CO2": round(float(520 + 30 * daily + rng.normal(0, 6)), 4),
            "NH3": round(float(3.5 + 0.4 * daily + rng.normal(0, 0.08)), 4),
        },
        "breath-rate": round(float(28 + 2 * daily + rng.normal(0, 0.4)), 4),
        "TemperatureData": {
            "rectal-temperature": round(float(38.7 + 0.15 * daily + rng.normal(0, 0.04)), 4),
            "back-temperature": round(float(37.1 + 0.12 * daily + rng.normal(0, 0.04)), 4),
            "neck-temperature": round(float(37.4 + 0.12 * daily + rng.normal(0, 0.04)), 4),
            "head-temperature": round(float(36.9 + 0.10 * daily + rng.normal(0, 0.04)), 4),
        },
        "FeedingAndManagementData": {
            "ventilation-rate": round(float(1.8 + 0.2 * daily), 4),
            "feedstuff_volume": round(float(3.2 + 0.5 * max(daily, 0)), 4),
            "watersupply": round(float(12 + 1.2 * max(daily, 0)), 4),
        },
    }


def generate_sample_json(
    output_dir: str | Path,
    chambers: int = 2,
    days: int = 4,
    freq_minutes: int = 10,
    seed: int = 42,
) -> int:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    periods = int(days * 24 * 60 / freq_minutes)
    start = pd.Timestamp("2026-01-01 00:00")

    count = 0
    for chamber_idx in range(1, chambers + 1):
        chamber = f"sample-{chamber_idx:02d}"
        for step in range(periods):
            dt = start + pd.Timedelta(minutes=freq_minutes * step)
            record = make_record(chamber, dt, step, rng)
            path = output / f"{chamber}_{dt.strftime('%Y%m%d_%H%M')}.json"
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic AI Hub-like JSON records.")
    parser.add_argument("--output-dir", default="data/sample_json")
    parser.add_argument("--chambers", type=int, default=2)
    parser.add_argument("--days", type=int, default=4)
    parser.add_argument("--freq-minutes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = generate_sample_json(
        output_dir=args.output_dir,
        chambers=args.chambers,
        days=args.days,
        freq_minutes=args.freq_minutes,
        seed=args.seed,
    )
    print(f"generated records: {count}")


if __name__ == "__main__":
    main()
