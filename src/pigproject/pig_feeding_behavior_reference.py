"""Build a normal feeding-behavior reference table from dataset 5126661.

Source: `feedingbehaviour.txt` -- 587 finishing pigs, one summary row per pig
covering the whole feeding period (not a time series; `age1`/`BWs` are
recorded at slaughter). Units are defined in
`data_description_for_feeding_behaviour.xlsx`:

- `DFIkg_day`: daily feed intake, kg/day
- `NDVvisits_day`: feeder visits/day
- `FOmin_day`: feeder occupation, minutes/day
- `FIVg_visit`: feed intake per visit, g/visit
- `DUVmin_visit`: visit duration, minutes/visit
- `FRg_min_day`: feeding rate, g/minute

This is used as a normal-range reference for `feed_drop` thresholds, not as
training data (no time axis, no disease/health labels).

`DFIkg_day` (kg/pig/day) is the only column with a directly unit-matched
counterpart in the ClearFarm dataset (`daily_feed_intake_per_pig_kg`,
`clearfarm_processing.py`), so the ClearFarm comparison in this module is
limited to that one pair -- other columns (feeding rate, visit counts) use
different units or aggregation levels across the two datasets and are not
compared to avoid an apples-to-oranges claim.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


DEFAULT_INPUT = "data/raw/external/pig_feeding_behavior_5126661/feedingbehaviour.txt"
DEFAULT_CLEARFARM_FEEDING_DAY = "data/processed/external/clearfarm/clearfarm_feeding_day.csv"
DEFAULT_ARTIFACT_DIR = "artifacts/pig_feeding_behavior_5126661"

FEATURE_COLUMNS = [
    "DFIkg_day",
    "NDVvisits_day",
    "FOmin_day",
    "FIVg_visit",
    "DUVmin_visit",
    "FRg_min_day",
]


def load_feeding_reference(path: str | Path = DEFAULT_INPUT) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    df["sex"] = df["sex"].astype(str)
    return df


def summarize_distribution(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    columns = columns or FEATURE_COLUMNS
    rows = []
    for col in columns:
        series = df[col].dropna()
        rows.append(
            {
                "feature": col,
                "mean": float(series.mean()),
                "std": float(series.std()),
                "min": float(series.min()),
                "p25": float(series.quantile(0.25)),
                "median": float(series.median()),
                "p75": float(series.quantile(0.75)),
                "max": float(series.max()),
            }
        )
    return pd.DataFrame(rows)


def summarize_by_sex(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    columns = columns or FEATURE_COLUMNS
    grouped = df.groupby("sex")[columns].agg(["mean", "std"])
    grouped.columns = [f"{feature}_{stat}" for feature, stat in grouped.columns]
    return grouped.reset_index()


def compare_with_clearfarm(
    df: pd.DataFrame, clearfarm_feeding_day_path: str | Path = DEFAULT_CLEARFARM_FEEDING_DAY
) -> pd.DataFrame | None:
    path = Path(clearfarm_feeding_day_path)
    if not path.exists():
        return None
    clearfarm = pd.read_csv(path)
    if "daily_feed_intake_per_pig_kg" not in clearfarm.columns:
        return None
    reference = df["DFIkg_day"].dropna()
    clearfarm_intake = clearfarm["daily_feed_intake_per_pig_kg"].dropna()
    return pd.DataFrame(
        [
            {
                "source": "5126661 (개체별 요약, 육성돈)",
                "n": len(reference),
                "median_kg_day": float(reference.median()),
                "p25_kg_day": float(reference.quantile(0.25)),
                "p75_kg_day": float(reference.quantile(0.75)),
            },
            {
                "source": "ClearFarm (pen-day 집계, 육성-비육돈)",
                "n": len(clearfarm_intake),
                "median_kg_day": float(clearfarm_intake.median()),
                "p25_kg_day": float(clearfarm_intake.quantile(0.25)),
                "p75_kg_day": float(clearfarm_intake.quantile(0.75)),
            },
        ]
    )


def write_report(
    output_dir: Path,
    df: pd.DataFrame,
    distribution: pd.DataFrame,
    by_sex: pd.DataFrame,
    clearfarm_compare: pd.DataFrame | None,
) -> Path:
    lines = [
        "# Pig Feeding Behavior (5126661) 정상 급이 reference",
        "",
        "데이터 출처: Mendeley/Dryad `5126661` -- 육성돈 587마리, 개체별 급이 행동 요약 "
        "(시계열 아님, `age1`/`BWs`는 출하 시점 값)",
        "",
        f"- pigs: `{len(df)}`",
        f"- sex: {df['sex'].value_counts().to_dict()}",
        f"- series(분만 batch) 수: `{df['series'].nunique()}`",
        f"- station 수: `{df['station'].nunique()}`",
        "",
        "## 전체 분포",
        "",
        dataframe_to_markdown(distribution),
        "",
        "## 성별 평균/표준편차",
        "",
        dataframe_to_markdown(by_sex),
    ]

    if clearfarm_compare is not None:
        lines += [
            "",
            "## ClearFarm과 일일 급이량(kg/day) 비교",
            "",
            "단위가 정확히 일치하는 컬럼(`DFIkg_day` vs `daily_feed_intake_per_pig_kg`, 둘 다 kg/마리/일)만 비교합니다. "
            "다른 컬럼(급이 속도, 방문 횟수)은 두 데이터셋의 집계 단위가 달라 비교하지 않습니다.",
            "",
            dataframe_to_markdown(clearfarm_compare),
        ]
    else:
        lines += [
            "",
            "## ClearFarm 비교",
            "",
            "ClearFarm `clearfarm_feeding_day.csv`가 없어 비교를 건너뜁니다. "
            "`pig-build-clearfarm-pen-day`를 먼저 실행하세요.",
        ]

    lines += [
        "",
        "## 판단",
        "",
        "- 이 데이터는 시계열이 아니라 개체별 요약이라 lead-time 평가에는 쓰지 않습니다.",
        "- `feed_drop` rule의 정상 일일 급이량 범위(대략 kg/day 단위)를 잡을 때 참고 분포로만 사용합니다.",
    ]

    report = output_dir / "feeding_reference_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_feeding_reference(
    input_path: str | Path = DEFAULT_INPUT,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    clearfarm_feeding_day_path: str | Path = DEFAULT_CLEARFARM_FEEDING_DAY,
) -> pd.DataFrame:
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)

    df = load_feeding_reference(input_path)
    distribution = summarize_distribution(df)
    by_sex = summarize_by_sex(df)
    clearfarm_compare = compare_with_clearfarm(df, clearfarm_feeding_day_path)

    distribution.to_csv(artifact_path / "feeding_reference_summary.csv", index=False)
    by_sex.to_csv(artifact_path / "feeding_reference_by_sex.csv", index=False)
    if clearfarm_compare is not None:
        clearfarm_compare.to_csv(artifact_path / "feeding_reference_clearfarm_compare.csv", index=False)
    write_report(artifact_path, df, distribution, by_sex, clearfarm_compare)
    return distribution


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normal feeding-behavior reference table from dataset 5126661.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--clearfarm-feeding-day", default=DEFAULT_CLEARFARM_FEEDING_DAY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    distribution = build_feeding_reference(
        input_path=args.input,
        artifact_dir=args.artifact_dir,
        clearfarm_feeding_day_path=args.clearfarm_feeding_day,
    )
    print(dataframe_to_markdown(distribution))


if __name__ == "__main__":
    main()
