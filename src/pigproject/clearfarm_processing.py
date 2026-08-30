"""Build pen-day features from the ClearFarm growing-finishing pig dataset."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown

DEFAULT_INPUT_DIR = "data/raw/external/clearfarm_growing_finishing"
DEFAULT_OUTPUT_DIR = "data/processed/external/clearfarm"
DEFAULT_ARTIFACT_DIR = "artifacts/external/clearfarm"

HEALTH_COLUMNS = [
    "hudd",
    "cough",
    "sneeze",
    "hyg_pen",
    "hyg_drink",
    "hyg_feed",
    "diar",
    "les_front",
    "les_mid",
    "les_rear",
    "flank_dam",
    "flank_necr",
    "tail_dam",
    "tail_necr",
    "eartip_dam",
    "eartip_necr",
    "earbas_dam",
    "earbas_necr",
    "conjunc",
    "lame",
    "burs",
    "ear_blue",
    "pump",
    "pant",
    "hernia",
    "rect_prol",
    "shiv",
    "bcs",
]


def parse_experiment_number(path: str | Path) -> int:
    match = re.search(r"Exp(\d+)", str(path))
    if not match:
        raise ValueError(f"Could not parse experiment number from {path}")
    return int(match.group(1))


def parse_clearfarm_date(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip()
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    digits8 = text.str.fullmatch(r"\d{8}", na=False)
    out.loc[digits8] = pd.to_datetime(text.loc[digits8], format="%Y%m%d", errors="coerce")

    iso = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}.*", na=False)
    out.loc[iso] = pd.to_datetime(text.loc[iso], errors="coerce")

    slash = text.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}.*", na=False)
    out.loc[slash] = pd.to_datetime(text.loc[slash], dayfirst=True, errors="coerce")

    remaining = out.isna() & text.notna()
    out.loc[remaining] = pd.to_datetime(text.loc[remaining], errors="coerce")
    return out.dt.normalize()


def normalize_pen_value(value: object, experiment: int) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if re.fullmatch(r"[A-Z]\d\.\d", text):
        return text
    if re.fullmatch(r"[A-Z]\d", text):
        return f"{text}.{experiment}"
    return text


def parse_exp1_ivog_station(value: object) -> float:
    """Convert Exp1 health-sheet IVOG labels such as F2/F10 to station numbers."""
    if pd.isna(value):
        return np.nan
    text = str(value).strip().upper()
    match = re.fullmatch(r"F(\d+)", text)
    if match:
        return float(match.group(1))
    return float(pd.to_numeric(text, errors="coerce"))


def load_station_pen_map(input_dir: str | Path) -> pd.DataFrame:
    rows = []
    for path in sorted(Path(input_dir).glob("Exp*/*Pig registration all info combined.csv")):
        experiment = parse_experiment_number(path)
        df = pd.read_csv(path)
        station_col = "station" if "station" in df.columns else "ivog"
        if station_col not in df.columns or "pen" not in df.columns:
            continue
        temp = df[[station_col, "pen"]].dropna().copy()
        temp["experiment"] = experiment
        temp["station"] = pd.to_numeric(temp[station_col], errors="coerce")
        temp["pen_id"] = temp["pen"].map(lambda x: normalize_pen_value(x, experiment))
        grouped = temp.dropna(subset=["station", "pen_id"]).groupby(["experiment", "station", "pen_id"]).size()
        for (exp, station, pen_id), count in grouped.items():
            rows.append({"experiment": exp, "station": int(station), "pen_id": pen_id, "registered_pigs": int(count)})
    mapping = pd.DataFrame(rows)
    if mapping.empty:
        return pd.DataFrame(columns=["experiment", "station", "pen_id", "registered_pigs"])
    return mapping.sort_values(["experiment", "station", "pen_id"]).reset_index(drop=True)


def build_feeding_day(input_dir: str | Path, station_map: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(input_dir).glob("Exp*/*Feeding data.csv")):
        experiment = parse_experiment_number(path)
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        if "pig.short" in df.columns and "pig" not in df.columns:
            df = df.rename(columns={"pig.short": "pig"})
        df["experiment"] = experiment
        df["date"] = parse_clearfarm_date(df["date"])
        df["station"] = pd.to_numeric(df["station"], errors="coerce")
        df["pig"] = pd.to_numeric(df["pig"], errors="coerce")
        for col in ["intake", "duration", "rate"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        tattoo = df.get("tattoo", pd.Series("", index=df.index)).astype("string").str.upper()
        df["is_filling_or_ghost"] = tattoo.str.contains("FILLING|GHOST", na=False) | (df["pig"].fillna(0) == 0)
        df["is_valid_feed_visit"] = (~df["is_filling_or_ghost"]) & (df["intake"] > 0) & (df["duration"] > 0)
        merged = df.merge(station_map, on=["experiment", "station"], how="left")
        frames.append(merged)
    all_feed = pd.concat(frames, ignore_index=True)
    valid_intake = all_feed["intake"].where(all_feed["is_valid_feed_visit"], 0)
    all_feed["valid_intake_kg"] = valid_intake
    all_feed["valid_duration_sec"] = all_feed["duration"].where(all_feed["is_valid_feed_visit"])
    all_feed["valid_rate"] = all_feed["rate"].where(all_feed["is_valid_feed_visit"])
    grouped = (
        all_feed.groupby(["experiment", "pen_id", "date"], dropna=False)
        .agg(
            feed_records=("intake", "size"),
            valid_feed_visits=("is_valid_feed_visit", "sum"),
            filling_or_ghost_records=("is_filling_or_ghost", "sum"),
            daily_feed_intake_kg=("valid_intake_kg", "sum"),
            mean_visit_duration_sec=("valid_duration_sec", "mean"),
            mean_feed_rate=("valid_rate", "mean"),
            active_feeding_pigs=("pig", lambda s: int(s[all_feed.loc[s.index, "is_valid_feed_visit"]].nunique())),
            stations=("station", "nunique"),
        )
        .reset_index()
    )
    grouped = grouped.dropna(subset=["pen_id", "date"])
    grouped["daily_feed_intake_per_pig_kg"] = grouped["daily_feed_intake_kg"] / grouped["active_feeding_pigs"].replace(0, np.nan)
    grouped = grouped.sort_values(["experiment", "pen_id", "date"])
    grouped["feed_intake_rolling_3d_kg"] = grouped.groupby(["experiment", "pen_id"])["daily_feed_intake_kg"].transform(
        lambda s: s.rolling(3, min_periods=1).mean()
    )
    grouped["feed_drop_pct_1d"] = grouped.groupby(["experiment", "pen_id"])["daily_feed_intake_kg"].pct_change() * -100
    grouped["feed_drop_pct_3d"] = (
        (grouped["feed_intake_rolling_3d_kg"] - grouped["daily_feed_intake_kg"])
        / grouped["feed_intake_rolling_3d_kg"].replace(0, np.nan)
        * 100
    )
    return grouped.reset_index(drop=True)


def build_feeding_hour(input_dir: str | Path, station_map: pd.DataFrame) -> pd.DataFrame:
    """Pen-hour feed intake -- the resolution `feed_drop`'s rolling z-score needs.

    `clearfarm_feeding_day.csv` collapses each pen to one row per day, which
    leaves only 3 points in any 3-day rolling window and caps the z-score at
    +-1.1547 (see `clearfarm_rule_validation.py`), well short of the rule's
    -1.5 threshold. The raw feeding log has a real timestamp per visit
    (~229 valid visits/pen/day on average), so aggregating to pen-hour
    instead of pen-day gives the 3-day window dozens of points instead of 3.
    """
    frames = []
    for path in sorted(Path(input_dir).glob("Exp*/*Feeding data.csv")):
        experiment = parse_experiment_number(path)
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        if "pig.short" in df.columns and "pig" not in df.columns:
            df = df.rename(columns={"pig.short": "pig"})
        df["experiment"] = experiment
        df["date"] = parse_clearfarm_date(df["date"])
        df["station"] = pd.to_numeric(df["station"], errors="coerce")
        df["pig"] = pd.to_numeric(df["pig"], errors="coerce")
        df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
        df["intake"] = pd.to_numeric(df["intake"], errors="coerce")
        df["duration"] = pd.to_numeric(df["duration"], errors="coerce")
        tattoo = df.get("tattoo", pd.Series("", index=df.index)).astype("string").str.upper()
        is_filling_or_ghost = tattoo.str.contains("FILLING|GHOST", na=False) | (df["pig"].fillna(0) == 0)
        is_valid_feed_visit = (~is_filling_or_ghost) & (df["intake"] > 0) & (df["duration"] > 0)
        df["valid_intake_kg"] = df["intake"].where(is_valid_feed_visit, 0)
        df["is_valid_feed_visit"] = is_valid_feed_visit
        merged = df.merge(station_map, on=["experiment", "station"], how="left")
        frames.append(merged)
    all_feed = pd.concat(frames, ignore_index=True)
    all_feed = all_feed.dropna(subset=["pen_id", "date", "hour"])
    all_feed["datetime"] = all_feed["date"] + pd.to_timedelta(all_feed["hour"], unit="h")
    grouped = (
        all_feed.groupby(["experiment", "pen_id", "datetime"], dropna=False)
        .agg(feed_intake_kg=("valid_intake_kg", "sum"), feed_visits=("is_valid_feed_visit", "sum"))
        .reset_index()
    )
    return grouped.sort_values(["experiment", "pen_id", "datetime"]).reset_index(drop=True)


def build_climate_day(input_dir: str | Path) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(input_dir).glob("Exp*/*Climate data.csv")):
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        df["experiment"] = pd.to_numeric(df["experiment"], errors="coerce").astype("Int64")
        df["date"] = parse_clearfarm_date(df["date"])
        df["pen_id"] = [normalize_pen_value(v, int(e)) for v, e in zip(df["pen"], df["experiment"])]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        kind = df["type"].astype("string").str.lower()
        df["measure"] = np.select(
            [kind.str.contains("co2", na=False), kind.str.contains("ammonia", na=False), kind.str.contains("hum", na=False), kind.str.contains("temp", na=False)],
            ["co2", "ammonia", "humidity", "temperature"],
            default="other",
        )
        frames.append(df[["experiment", "pen_id", "date", "measure", "value"]])
    if not frames:
        return pd.DataFrame(columns=["experiment", "pen_id", "date"])
    climate = pd.concat(frames, ignore_index=True).dropna(subset=["experiment", "pen_id", "date", "value"])
    agg = climate.groupby(["experiment", "pen_id", "date", "measure"])["value"].agg(["mean", "max", "min"]).reset_index()
    pivot = agg.pivot_table(index=["experiment", "pen_id", "date"], columns="measure", values=["mean", "max", "min"])
    pivot.columns = [f"{measure}_{stat}" for stat, measure in pivot.columns]
    return pivot.reset_index().sort_values(["experiment", "pen_id", "date"]).reset_index(drop=True)


def build_health_day(input_dir: str | Path, station_map: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(input_dir).glob("Exp*/*On-farm observations.xlsx")):
        experiment = parse_experiment_number(path)
        xl = pd.ExcelFile(path)
        sheet = "Raw data" if "Raw data" in xl.sheet_names else "Raw health data"
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = [str(c).strip() for c in df.columns]
        df["experiment"] = experiment
        df["date"] = parse_clearfarm_date(df["date"])
        temp = df.copy()
        if experiment == 1 and "ivog" in temp.columns:
            # Exp1 stores IVOG labels such as F2/F10. Treat the number as the
            # feeding-station id, then reuse the registration-derived station->pen map.
            temp["station"] = temp["ivog"].map(parse_exp1_ivog_station)
            temp = temp.merge(
                station_map[["experiment", "station", "pen_id"]].drop_duplicates(),
                on=["experiment", "station"],
                how="left",
            )
        else:
            temp["pen_id"] = temp["pen"].map(lambda x: normalize_pen_value(x, experiment))
        available = [c for c in HEALTH_COLUMNS if c in temp.columns]
        for col in available:
            temp[col] = pd.to_numeric(temp[col], errors="coerce")
        if not available:
            continue
        agg = temp.groupby(["experiment", "pen_id", "date"], dropna=False).agg(
            health_observation_rows=(available[0], "size"),
            observed_pigs=("pig", lambda s: int(pd.to_numeric(s, errors="coerce").dropna().nunique())) if "pig" in temp.columns else (available[0], "size"),
        )
        sums = temp.groupby(["experiment", "pen_id", "date"], dropna=False)[available].sum(min_count=1).add_suffix("_sum")
        maxes = temp.groupby(["experiment", "pen_id", "date"], dropna=False)[available].max().add_suffix("_max")
        out = pd.concat([agg, sums, maxes], axis=1).reset_index()
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=["experiment", "pen_id", "date"])
    return pd.concat(frames, ignore_index=True).dropna(subset=["pen_id", "date"]).sort_values(["experiment", "pen_id", "date"]).reset_index(drop=True)


def add_date_parts(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    out["is_jan_to_may"] = out["month"].between(1, 5)
    return out


def build_pen_day(input_dir: str | Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    station_map = load_station_pen_map(input_dir)
    feeding = build_feeding_day(input_dir, station_map)
    climate = build_climate_day(input_dir)
    health = build_health_day(input_dir, station_map)
    keys = ["experiment", "pen_id", "date"]
    pen_day = feeding.merge(climate, on=keys, how="outer").merge(health, on=keys, how="outer")
    pen_day = add_date_parts(pen_day.sort_values(keys).reset_index(drop=True))
    return pen_day, {"station_pen_map": station_map, "feeding_day": feeding, "climate_day": climate, "health_day": health}


def write_outputs(input_dir: str | Path, output_dir: str | Path, artifact_dir: str | Path) -> Path:
    output = Path(output_dir)
    artifacts = Path(artifact_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    pen_day, components = build_pen_day(input_dir)
    pen_day.to_csv(output / "clearfarm_pen_day.csv", index=False)
    for name, df in components.items():
        df.to_csv(output / f"clearfarm_{name}.csv", index=False)

    summary_rows = [
        {"table": "clearfarm_pen_day", "rows": len(pen_day), "cols": len(pen_day.columns), "pens": pen_day["pen_id"].nunique(), "date_min": pen_day["date"].min(), "date_max": pen_day["date"].max()},
    ]
    for name, df in components.items():
        summary_rows.append({"table": name, "rows": len(df), "cols": len(df.columns), "pens": df["pen_id"].nunique() if "pen_id" in df.columns else np.nan, "date_min": df["date"].min() if "date" in df.columns else pd.NaT, "date_max": df["date"].max() if "date" in df.columns else pd.NaT})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(artifacts / "clearfarm_pen_day_summary.csv", index=False)

    seasonal = pen_day.groupby(["year", "month", "is_jan_to_may"], dropna=False).agg(
        pen_days=("pen_id", "size"),
        pens=("pen_id", "nunique"),
        feed_days=("daily_feed_intake_kg", lambda s: int(s.notna().sum())),
        climate_days=("temperature_mean", lambda s: int(s.notna().sum()) if "temperature_mean" in pen_day.columns else 0),
        health_days=("health_observation_rows", lambda s: int(s.notna().sum()) if "health_observation_rows" in pen_day.columns else 0),
    ).reset_index()
    seasonal.to_csv(artifacts / "clearfarm_seasonal_availability.csv", index=False)

    lines = [
        "# ClearFarm Pen-Day Build Report",
        "",
        f"- input_dir: `{input_dir}`",
        f"- output: `{output / 'clearfarm_pen_day.csv'}`",
        "",
        "## Table Summary",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Seasonal Availability",
        "",
        dataframe_to_markdown(seasonal),
        "",
        "## 해석",
        "",
        "- ClearFarm은 실제 비육돈 농장 관측 데이터라 feed/environment/health rule 검증에 바로 사용할 수 있습니다.",
        "- 1-5월 데이터는 Exp1의 2021년 1-2월과 Exp3의 2022년 5월에 존재합니다.",
        "- 다음 단계는 이 pen-day 테이블로 feed_drop, environment_failure, respiratory 관찰 이벤트를 정의하는 것입니다.",
    ]
    report = artifacts / "clearfarm_pen_day_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ClearFarm pen-day feature tables.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = write_outputs(args.input_dir, args.output_dir, args.artifact_dir)
    print(f"Wrote {report}")


if __name__ == "__main__":
    main()
