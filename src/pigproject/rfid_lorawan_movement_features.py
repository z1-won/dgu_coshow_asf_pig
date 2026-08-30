"""Build pig-hour/pig-day activity baseline features from the RFID-LoRaWAN movement dataset.

Source: `MOVEMENT_Final.csv` -- 16 finishing pigs, 20 days before slaughter,
RFID-LoRaWAN positioning, Norway 2023 (see `This dataset.docx`).

The dataset's own description says each row is already one pig x day x hour
record with a pre-aggregated hourly distance. The actual file does not match
that: the same `(pid_id, Day_s, Hour)` key repeats up to ~180 times with
*different* distance values (confirmed by inspection, not assumed), which is
consistent with the file being closer to the "1-second resolution raw
detections" the doc also mentions, exported before the hourly aggregation
step. This module treats every row as a sub-hourly movement segment and
**sums** distance per `(pig, day, hour)` -- the safe choice either way, since
it is a no-op if a key truly has only one row.

No disease/health labels exist in this dataset, so it is used only as a
normal-activity baseline (variability range, day-to-day drop candidates),
never for recall/precision evaluation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


DATASET_KEY = "rfid_lorawan_movement"
DEFAULT_INPUT = "data/raw/external/rfid_lorawan_movement_17266727/MOVEMENT_Final.csv"
DEFAULT_HOUR_OUTPUT = "data/processed/external/rfid_lorawan/rfid_pig_hour.csv"
DEFAULT_DAY_OUTPUT = "data/processed/external/rfid_lorawan/rfid_pig_day.csv"
DEFAULT_ARTIFACT_DIR = "artifacts/rfid_lorawan_movement"

MAX_HOURS_PER_DAY = 24
LOW_DATA_HOUR_THRESHOLD = 20
# Not confirmed by the source metadata (no lighting schedule is documented) --
# a commonly used dark-period window for commercial pig barns, kept as an
# explicit, callable-out assumption rather than a silently baked-in constant.
NIGHT_HOURS = {21, 22, 23, 0, 1, 2, 3, 4, 5}


def load_movement(path: str | Path = DEFAULT_INPUT) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df.columns = [col.strip() for col in df.columns]
    df = df.rename(columns={"pid_id": "pig_id", "Day_s": "day"})
    df["pig_id"] = df["pig_id"].astype(str)
    df["hour"] = df["Hour"].str.slice(0, 2).astype(int)
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    return df.dropna(subset=["distance"])[["pig_id", "day", "hour", "distance"]]


def build_pig_hour(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby(["pig_id", "day", "hour"])
        .agg(distance_sum_hour=("distance", "sum"), reading_count_hour=("distance", "size"))
        .reset_index()
    )
    return out.sort_values(["pig_id", "day", "hour"]).reset_index(drop=True)


def build_pig_day(pig_hour: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (pig_id, day), group in pig_hour.groupby(["pig_id", "day"]):
        night_distance = group.loc[group["hour"].isin(NIGHT_HOURS), "distance_sum_hour"].sum()
        total_distance = group["distance_sum_hour"].sum()
        rows.append(
            {
                "pig_id": pig_id,
                "day": day,
                "distance_sum_day": total_distance,
                "distance_mean_hour": float(group["distance_sum_hour"].mean()),
                "distance_std_hour": float(group["distance_sum_hour"].std()) if len(group) > 1 else 0.0,
                "hours_observed": int(group["hour"].nunique()),
                "night_activity_ratio": float(night_distance / total_distance) if total_distance else np.nan,
                "low_data_day": group["hour"].nunique() < LOW_DATA_HOUR_THRESHOLD,
            }
        )
    return pd.DataFrame(rows).sort_values(["pig_id", "day"]).reset_index(drop=True)


def add_activity_drop_features(pig_day: pd.DataFrame) -> pd.DataFrame:
    out = pig_day.copy()
    out["activity_drop_pct_1d"] = np.nan
    out["activity_drop_zscore"] = np.nan
    for pig_id, group in out.groupby("pig_id"):
        idx = group.index
        prev = group["distance_sum_day"].shift(1)
        pct_change = (group["distance_sum_day"] - prev) / prev
        out.loc[idx, "activity_drop_pct_1d"] = pct_change
        pig_mean = group["distance_sum_day"].mean()
        pig_std = group["distance_sum_day"].std()
        if pig_std:
            out.loc[idx, "activity_drop_zscore"] = (group["distance_sum_day"] - pig_mean) / pig_std
        else:
            out.loc[idx, "activity_drop_zscore"] = 0.0
    return out


def write_report(
    output_dir: Path,
    raw: pd.DataFrame,
    pig_hour: pd.DataFrame,
    pig_day: pd.DataFrame,
) -> Path:
    possible_pig_days = raw["pig_id"].nunique() * raw["day"].nunique()
    observed_pig_days = len(pig_day)
    low_data_days = int(pig_day["low_data_day"].sum())

    per_pig = (
        pig_day.groupby("pig_id")
        .agg(
            days_observed=("day", "nunique"),
            mean_distance_sum_day=("distance_sum_day", "mean"),
            std_distance_sum_day=("distance_sum_day", "std"),
            mean_night_activity_ratio=("night_activity_ratio", "mean"),
        )
        .reset_index()
    )

    biggest_drop = pig_day.dropna(subset=["activity_drop_pct_1d"]).nsmallest(5, "activity_drop_pct_1d")

    rows = [
        "# RFID-LoRaWAN Movement 활동량 baseline 리포트",
        "",
        "데이터 출처: Zenodo/Dryad `17266727` -- 육성돈 16마리, 출하 전 20일, RFID-LoRaWAN 실내 위치추적, "
        "노르웨이 상업농장 2023 (`This dataset.docx`)",
        "",
        f"- 원본 row: `{len(raw)}`",
        f"- 가능한 pig x day 조합: `{possible_pig_days}`",
        f"- 실제 데이터가 있는 pig x day: `{observed_pig_days}` "
        f"({observed_pig_days / possible_pig_days:.1%})",
        f"- 24시간 중 20시간 미만만 관측된 저품질 day: `{low_data_days}` / `{observed_pig_days}`",
        "",
        "## 데이터 이슈",
        "",
        "- 원본 문서(`This dataset.docx`)는 \"각 행이 이미 pig x day x hour 단위로 집계된 시간당 거리\"라고 "
        "설명하지만, 실제 파일은 같은 `(pig_id, day, hour)` 키가 최대 약 180번까지 서로 다른 distance 값으로 "
        "반복됩니다 -- 1초 단위 원시 감지 기록이 시간 단위로 집계되기 전 상태로 보입니다. "
        "이 모듈은 같은 키의 distance를 **합산**해서 시간당 총 이동거리를 재구성합니다.",
        "- `night_activity_ratio`의 야간 시간대(21시~05시)는 원본 메타데이터에 조명 스케줄이 없어 "
        "**확인되지 않은 가정**입니다.",
        "",
        "## 개체별 요약",
        "",
        dataframe_to_markdown(per_pig),
        "",
        "## 활동량 급감(1일 대비) 상위 5건",
        "",
        dataframe_to_markdown(biggest_drop[["pig_id", "day", "distance_sum_day", "activity_drop_pct_1d", "activity_drop_zscore", "low_data_day"]]),
        "",
        "## 판단",
        "",
        "- 이 데이터에는 질병/건강 이벤트 라벨이 없으므로 recall/precision 평가에는 쓸 수 없습니다.",
        "- `activity_drop_zscore`는 개체 스스로의 20일 평균/표준편차 기준이라, "
        "AI Hub 622 activity_drop rule의 정상 변동폭을 가늠하는 외부 baseline 후보로만 사용합니다.",
        "- `low_data_day=True`인 행은 실제 활동량 감소가 아니라 태그 통신 두절일 수 있으므로 "
        "activity_drop 후보에서 우선 제외하거나 별도 표시가 필요합니다.",
    ]
    report = output_dir / "rfid_lorawan_movement_baseline_report.md"
    report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return report


def build_rfid_movement_features(
    input_path: str | Path = DEFAULT_INPUT,
    hour_output: str | Path = DEFAULT_HOUR_OUTPUT,
    day_output: str | Path = DEFAULT_DAY_OUTPUT,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    hour_path = Path(hour_output)
    hour_path.parent.mkdir(parents=True, exist_ok=True)
    day_path = Path(day_output)
    day_path.parent.mkdir(parents=True, exist_ok=True)

    raw = load_movement(input_path)
    pig_hour = build_pig_hour(raw)
    pig_day = add_activity_drop_features(build_pig_day(pig_hour))

    pig_hour.to_csv(hour_path, index=False)
    pig_day.to_csv(day_path, index=False)
    pig_hour.to_csv(artifact_path / "rfid_pig_hour.csv", index=False)
    pig_day.to_csv(artifact_path / "rfid_pig_day.csv", index=False)
    write_report(artifact_path, raw, pig_hour, pig_day)
    return pig_hour, pig_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RFID-LoRaWAN pig-hour/pig-day movement baseline features.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--hour-output", default=DEFAULT_HOUR_OUTPUT)
    parser.add_argument("--day-output", default=DEFAULT_DAY_OUTPUT)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pig_hour, pig_day = build_rfid_movement_features(
        input_path=args.input,
        hour_output=args.hour_output,
        day_output=args.day_output,
        artifact_dir=args.artifact_dir,
    )
    print("pig_hour rows:", len(pig_hour))
    print("pig_day rows:", len(pig_day))


if __name__ == "__main__":
    main()
