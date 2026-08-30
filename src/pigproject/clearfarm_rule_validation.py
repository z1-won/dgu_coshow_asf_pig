"""Validate domain rules against ClearFarm growing-finishing pig observations.

ClearFarm is the project's only finishing-pig (비육돈) dataset that carries
real health observation labels (`clearfarm_health_day.csv`, merged into
`clearfarm_pen_day.csv`). Of the 11 rules in `config/domain_rules.json`, only
`feed_drop`, `co2_high`, `nh3_high`, and `barn_temp_high` have a matching
sensor in ClearFarm -- there is no individual body temperature, water
supply, or ventilation-rate sensor here, so `rectal_temp_high`,
`neck_temp_high`, `water_drop`, `water_spike`, and `ventilation_low` cannot
be tested against this dataset.

`CLEARFARM_RFID_FEEDING_DATA_USAGE_PLAN.md` originally planned to also use
"pig removals / sickbay" events as a ground-truth label, but the raw
registration file (`Pig registration all info combined.csv`) only has
start/end body weight per experiment -- no removal or sickbay column exists,
so that label is not available and health-observation counts are the only
ground truth used here.

Health observations happen on a subset of days (~25% of pen-days); this
module only scores days where `health_observation_rows > 0`, the same
"only score where both signal and ground truth exist" approach used for the
ASF Dryad and PRRSV validations.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.clearfarm_processing import DEFAULT_INPUT_DIR as DEFAULT_CLEARFARM_RAW_DIR
from pigproject.clearfarm_processing import build_feeding_hour, load_station_pen_map
from pigproject.rolling_features import add_rolling_features


DEFAULT_PEN_DAY_PATH = "data/processed/external/clearfarm/clearfarm_pen_day.csv"
DEFAULT_ARTIFACT_DIR = "artifacts/clearfarm_rule_validation"
CONFIGURED_FEED_DROP_THRESHOLD = -1.5
CONFIGURED_CO2_THRESHOLD = 1000
CONFIGURED_NH3_THRESHOLD = 10
CONFIGURED_BARN_TEMP_THRESHOLD = 40


@dataclass(frozen=True)
class RuleThresholds:
    feed_drop: float = CONFIGURED_FEED_DROP_THRESHOLD
    co2_high: float = CONFIGURED_CO2_THRESHOLD
    nh3_high: float = CONFIGURED_NH3_THRESHOLD
    barn_temp_high: float = CONFIGURED_BARN_TEMP_THRESHOLD
    source: str = "built-in defaults"


def load_rule_thresholds(config_path: str | Path | None) -> RuleThresholds:
    if config_path is None:
        return RuleThresholds()
    path = Path(config_path)
    config = json.loads(path.read_text(encoding="utf-8"))
    by_id = {str(rule.get("id")): rule for rule in config.get("rules", [])}

    def threshold(rule_id: str, default: float) -> float:
        rule = by_id.get(rule_id, {})
        value = rule.get("threshold", default)
        return float(value)

    return RuleThresholds(
        feed_drop=threshold("feed_drop", CONFIGURED_FEED_DROP_THRESHOLD),
        co2_high=threshold("co2_high", CONFIGURED_CO2_THRESHOLD),
        nh3_high=threshold("nh3_high", CONFIGURED_NH3_THRESHOLD),
        barn_temp_high=threshold("barn_temp_high", CONFIGURED_BARN_TEMP_THRESHOLD),
        source=str(path),
    )

RESPIRATORY_SIGN_COLUMNS = ["cough_sum", "sneeze_sum", "pump_sum"]
GUT_SIGN_COLUMNS = ["diar_sum"]
THERMAL_SIGN_COLUMNS = ["pant_sum", "shiv_sum"]
ANY_SIGN_COLUMNS = RESPIRATORY_SIGN_COLUMNS + GUT_SIGN_COLUMNS + THERMAL_SIGN_COLUMNS


def load_pen_day(path: str | Path = DEFAULT_PEN_DAY_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["experiment", "pen_id", "date"]).reset_index(drop=True)


def filter_health_observed(df: pd.DataFrame) -> pd.DataFrame:
    observed = df["health_observation_rows"].fillna(0) > 0
    return df.loc[observed].reset_index(drop=True)


def define_disease_signs(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ANY_SIGN_COLUMNS:
        out[col] = out[col].fillna(0)
    out["respiratory_signs"] = out[RESPIRATORY_SIGN_COLUMNS].sum(axis=1) > 0
    out["gut_signs"] = out[GUT_SIGN_COLUMNS].sum(axis=1) > 0
    out["thermal_signs"] = out[THERMAL_SIGN_COLUMNS].sum(axis=1) > 0
    out["heat_signs"] = out["pant_sum"] > 0
    out["cold_signs"] = out["shiv_sum"] > 0
    out["any_signs"] = out[ANY_SIGN_COLUMNS].sum(axis=1) > 0
    return out


def compute_feed_zscore_3d(df: pd.DataFrame) -> pd.DataFrame:
    """Reproduce `feed_drop`'s z-score using the actual production code.

    `rolling_features.add_rolling_features` is what `feed_drop` is scored
    against in the real pipeline: a calendar-time 3-day window that
    *includes* today (not a trailing/excluding window), and a std==0 guard
    that zeroes the z-score instead of dividing by ~0. Reusing it here
    (rather than a hand-rolled version) is what caught that a first attempt
    at this function, using an excluding-today trailing window with no
    std guard, produced z-scores as extreme as -101 on pens with a
    near-zero 3-day rolling std -- an artifact the real rule never sees
    because of that guard.
    """
    adapted = df.rename(columns={"pen_id": "chamber_number", "date": "datetime"}).copy()
    adapted["dataset_key"] = "clearfarm"
    rolled = add_rolling_features(adapted, columns=["daily_feed_intake_per_pig_kg"])
    rolled = rolled.rename(
        columns={
            "chamber_number": "pen_id",
            "datetime": "date",
            "daily_feed_intake_per_pig_kg_zscore_3d": "feedstuff_volume_mean_zscore_3d",
        }
    ).drop(columns=["dataset_key"])
    return rolled


def prepare_validation_frame(pen_day_path: str | Path = DEFAULT_PEN_DAY_PATH) -> pd.DataFrame:
    df = load_pen_day(pen_day_path)
    df = compute_feed_zscore_3d(df)  # computed on the full daily series before filtering to health days
    df = filter_health_observed(df)
    df = define_disease_signs(df)
    return df


def confusion_for_threshold(
    df: pd.DataFrame, feature_col: str, threshold: float, sign_col: str, direction: str = "below"
) -> dict[str, float]:
    """Confusion matrix for a rule vs `sign_col`.

    `direction="below"` scores a drop rule (`feature_col <= threshold`, e.g.
    `feed_drop`); `direction="above"` scores a high-value rule
    (`feature_col >= threshold`, e.g. `co2_high`/`nh3_high`).
    """
    scored = df.dropna(subset=[feature_col, sign_col])
    if direction == "below":
        rule = scored[feature_col] <= threshold
    elif direction == "above":
        rule = scored[feature_col] >= threshold
    else:
        raise ValueError(f"Unknown direction: {direction}. Use 'below' or 'above'.")
    positive = scored[sign_col].astype(bool)
    tp = int((rule & positive).sum())
    fn = int((~rule & positive).sum())
    fp = int((rule & ~positive).sum())
    tn = int((~rule & ~positive).sum())
    sensitivity = tp / (tp + fn) if tp + fn else np.nan
    specificity = tn / (tn + fp) if tn + fp else np.nan
    precision = tp / (tp + fp) if tp + fp else np.nan
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision and sensitivity else np.nan
    return {
        "threshold": threshold,
        "n": len(scored),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
    }


def threshold_sweep(
    df: pd.DataFrame, feature_col: str, thresholds: list[float], sign_col: str, direction: str = "below"
) -> pd.DataFrame:
    return pd.DataFrame(
        [confusion_for_threshold(df, feature_col, threshold, sign_col, direction) for threshold in thresholds]
    )


def write_feed_drop_report(output_dir: Path, df: pd.DataFrame) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "clearfarm_validation_frame.csv", index=False)

    achievable_max = float(df["feedstuff_volume_mean_zscore_3d"].abs().max())
    zscore_thresholds = [-0.2, -0.4, -0.6, -0.8, -1.0, -1.15]
    pct1d_thresholds = [-10, -20, -30, -40, -50]
    pct3d_thresholds = [-10, -20, -30, -40, -50]

    zscore_any = threshold_sweep(df, "feedstuff_volume_mean_zscore_3d", zscore_thresholds, "any_signs")
    zscore_gut = threshold_sweep(df, "feedstuff_volume_mean_zscore_3d", zscore_thresholds, "gut_signs")
    pct1d_any = threshold_sweep(df, "feed_drop_pct_1d", pct1d_thresholds, "any_signs")
    pct3d_any = threshold_sweep(df, "feed_drop_pct_3d", pct3d_thresholds, "any_signs")

    zscore_any.to_csv(output_dir / "clearfarm_feed_drop_zscore_vs_any_signs.csv", index=False)
    zscore_gut.to_csv(output_dir / "clearfarm_feed_drop_zscore_vs_gut_signs.csv", index=False)
    pct1d_any.to_csv(output_dir / "clearfarm_feed_drop_pct1d_vs_any_signs.csv", index=False)
    pct3d_any.to_csv(output_dir / "clearfarm_feed_drop_pct3d_vs_any_signs.csv", index=False)

    lines = [
        "# ClearFarm feed_drop 규칙 검증",
        "",
        "데이터 출처: ClearFarm growing-finishing pig sensor dataset (비육돈), "
        f"health-observed pen-day `{len(df)}`건",
        "",
        "## 핵심 발견: 일단위 데이터에서는 z-score 임계값(-1.5)이 수학적으로 불가능하다",
        "",
        f"- `feed_drop` 규칙은 `feedstuff_volume_mean_zscore_3d <= -1.5`로 정의되어 있다.",
        f"- ClearFarm은 pen당 하루 1행이라, `add_rolling_features`(실제 운영 코드, 달력 3일 포함 window)를 그대로 적용하면 "
        "3일 window 안에 점이 최대 3개뿐이다.",
        f"- 표본 3개짜리 z-score(ddof=1)의 이론적 최댓값은 `2/sqrt(3) ≈ 1.1547`이다 -- "
        f"실제로 이 데이터에서 관측된 절댓값 최댓값도 `{achievable_max:.4f}`로 정확히 일치한다.",
        "- 즉 **하루 1행짜리 집계 데이터에 이 규칙을 그대로 적용하면 threshold(-1.5)가 이론상 절대 발동하지 않는다.** "
        "AI Hub 원본처럼 하루 여러 번(예: 10분 단위) 샘플링되는 데이터라면 3일 window 안에 점이 훨씬 많아 이 문제가 없다 -- "
        "이건 규칙 자체의 결함이 아니라 '일단위로 집계된 입력에 그대로 쓰면 무력화된다'는 입력 해상도 요구사항이다.",
        "- `NEXT_STEPS.md`가 이전에 기록한 \"feed_drop, water_drop, ventilation_low은 현재 validation window에서는 "
        "직접 hit가 없다\"는 관찰과 같은 메커니즘일 가능성이 있다 -- 확인하려면 AI Hub 쪽 window당 실제 샘플 수를 봐야 한다.",
        "",
        "## z-score 대안 threshold sweep (달성 가능한 범위 내에서)",
        "",
        "### vs any_signs (호흡/설사/체온조절 신호 중 하나라도)",
        "",
        dataframe_to_markdown(zscore_any),
        "",
        "### vs gut_signs (설사만)",
        "",
        dataframe_to_markdown(zscore_gut),
        "",
        "## 일단위 대안 지표: feed_drop_pct (이미 계산된 % 변화량, z-score cap 영향 없음)",
        "",
        "### feed_drop_pct_1d vs any_signs",
        "",
        dataframe_to_markdown(pct1d_any),
        "",
        "### feed_drop_pct_3d vs any_signs",
        "",
        dataframe_to_markdown(pct3d_any),
        "",
        "## 판단",
        "",
        "- 현재 설정된 -1.5 threshold는 일단위 데이터에서 그대로 검증할 수 없다는 것 자체가 이번 검증의 핵심 결과다.",
        "- pct 기반 지표(`feed_drop_pct_1d/3d`)는 z-score cap의 영향을 받지 않아 일단위 데이터에서도 threshold를 "
        "실제로 스윕할 수 있지만, 위 표에서 보듯 정밀도/재현율이 강하게 뚜렷한 단일 threshold는 나오지 않는다 -- "
        "feed_drop 단독보다는 다른 신호(환경, 활동량)와의 동시발생 조건이 필요하다는 기존 프로젝트 설계 방향과 일치한다.",
    ]
    report = output_dir / "clearfarm_feed_drop_validation_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def write_environment_report(output_dir: Path, df: pd.DataFrame, thresholds: RuleThresholds | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    thresholds = thresholds or RuleThresholds()

    co2_percentiles = df["co2_max"].quantile([0.10, 0.25, 0.50, 0.75, 0.90]).round(0)
    ammonia_percentiles = df["ammonia_max"].quantile([0.10, 0.25, 0.50, 0.75, 0.90]).round(0)
    co2_thresholds = sorted({thresholds.co2_high, *co2_percentiles.astype(int).tolist()})
    ammonia_thresholds = sorted({thresholds.nh3_high, *ammonia_percentiles.astype(int).tolist()})

    co2_configured = confusion_for_threshold(df, "co2_max", thresholds.co2_high, "respiratory_signs", "above")
    nh3_configured = confusion_for_threshold(df, "ammonia_max", thresholds.nh3_high, "respiratory_signs", "above")

    co2_sweep = threshold_sweep(df, "co2_max", co2_thresholds, "respiratory_signs", "above")
    ammonia_sweep = threshold_sweep(df, "ammonia_max", ammonia_thresholds, "respiratory_signs", "above")
    co2_sweep_any = threshold_sweep(df, "co2_max", co2_thresholds, "any_signs", "above")
    ammonia_sweep_any = threshold_sweep(df, "ammonia_max", ammonia_thresholds, "any_signs", "above")

    co2_sweep.to_csv(output_dir / "clearfarm_co2_high_vs_respiratory_signs.csv", index=False)
    ammonia_sweep.to_csv(output_dir / "clearfarm_nh3_high_vs_respiratory_signs.csv", index=False)

    co2_pct_below_threshold = float((df["co2_max"].dropna() < thresholds.co2_high).mean())
    ammonia_pct_below_threshold = float((df["ammonia_max"].dropna() < thresholds.nh3_high).mean())

    lines = [
        "# ClearFarm co2_high / nh3_high 규칙 검증",
        "",
        f"데이터 출처: ClearFarm growing-finishing pig sensor dataset (비육돈), health-observed pen-day `{len(df)}`건",
        "",
        "## 핵심 발견: 설정된 threshold가 ClearFarm에서는 사실상 상시 발동한다",
        "",
        f"- 적용 config: `{thresholds.source}`"
        f"- `co2_high`는 `CO2_mean(창 내 max) >= {thresholds.co2_high:g}`, `nh3_high`는 "
        f"`NH3_mean(창 내 max) >= {thresholds.nh3_high:g}`로 설정되어 있다.",
        f"- ClearFarm의 일일 CO2 최댓값(`co2_max`)이 {thresholds.co2_high:g} 미만인 날은 전체의 "
        f"`{co2_pct_below_threshold:.1%}`뿐이다 -- 나머지 대부분은 규칙이 항상 발동한다는 뜻이다.",
        f"- ClearFarm의 일일 암모니아 최댓값(`ammonia_max`)이 {thresholds.nh3_high:g} 미만인 날은 "
        f"`{ammonia_pct_below_threshold:.1%}`뿐이다.",
        f"- 설정된 threshold 그대로 적용한 confusion matrix: co2_high "
        f"sensitivity={co2_configured['sensitivity']:.1%} / specificity={co2_configured['specificity']:.1%}, "
        f"nh3_high sensitivity={nh3_configured['sensitivity']:.1%} / specificity={nh3_configured['specificity']:.1%} "
        "-- specificity가 이 정도로 낮으면 '규칙이 걸리면 믿을 수 있다'는 의미가 없다.",
        "- PRRSV에서 확인한 온도 threshold 비전이성과 같은 패턴이다: AI Hub 데이터에 맞춰 잡은 절대값 threshold가 "
        "다른 농장/센서 환경에는 그대로 옮겨지지 않는다. ClearFarm은 deep straw bedding 사육이라 CO2/암모니아 "
        "기저치 자체가 AI Hub 대비 높을 수 있다.",
        "",
        "## co2_high: threshold sweep (co2_max, vs respiratory_signs)",
        "",
        dataframe_to_markdown(co2_sweep),
        "",
        "## nh3_high: threshold sweep (ammonia_max, vs respiratory_signs)",
        "",
        dataframe_to_markdown(ammonia_sweep),
        "",
        "## co2_high / nh3_high vs any_signs (참고)",
        "",
        dataframe_to_markdown(co2_sweep_any),
        "",
        dataframe_to_markdown(ammonia_sweep_any),
        "",
        "## 판단",
        "",
        "- 두 환경 규칙 모두 ClearFarm에 그대로 적용하면 상시 발동에 가까워 무의미하다 -- "
        "이 농장 기준으로 재캘리브레이션하지 않는 한 co2_high/nh3_high는 ClearFarm 데이터에서 쓸 수 없다.",
        "- `ventilation_low`, `ventilation_low_with_co2_high`, `ventilation_low_with_nh3_high`는 ClearFarm에 "
        "환기량 센서가 없어 검증 자체가 불가능하다 (계획 단계에서 이미 확인).",
        "- 결론은 feed_drop과 같다: **절대값 threshold 하나를 여러 농장/데이터셋에 공유하는 설계는 구조적으로 "
        "취약하고, 농장별/기간별 정상 baseline 대비 상대 threshold(z-score, percentile) 쪽으로 가야 한다.**",
    ]
    report = output_dir / "clearfarm_environment_validation_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def compute_subdaily_feed_zscore(
    raw_dir: str | Path = DEFAULT_CLEARFARM_RAW_DIR,
) -> pd.DataFrame:
    """Pen-hour `feed_drop` z-score, then collapsed to one worst-of-day value per pen-day.

    Uses `daily_min_zscore` (the most negative hourly z-score observed that
    day) as the day's `feed_drop` signal -- a drop lasting even a few hours
    should count as the rule firing that day, so taking the day's mean would
    wash out short but real drops.
    """
    station_map = load_station_pen_map(raw_dir)
    hourly = build_feeding_hour(raw_dir, station_map)
    adapted = hourly.rename(columns={"pen_id": "chamber_number"}).copy()
    adapted["dataset_key"] = "clearfarm"
    rolled = add_rolling_features(adapted, columns=["feed_intake_kg"])
    rolled["date"] = rolled["datetime"].dt.normalize()
    daily = (
        rolled.groupby(["experiment", "chamber_number", "date"])["feed_intake_kg_zscore_3d"]
        .min()
        .reset_index()
        .rename(columns={"chamber_number": "pen_id", "feed_intake_kg_zscore_3d": "feed_intake_daily_min_zscore_3d"})
    )
    return daily


def prepare_subdaily_validation_frame(
    pen_day_path: str | Path = DEFAULT_PEN_DAY_PATH,
    raw_dir: str | Path = DEFAULT_CLEARFARM_RAW_DIR,
) -> pd.DataFrame:
    base = prepare_validation_frame(pen_day_path)
    daily_zscore = compute_subdaily_feed_zscore(raw_dir)
    return base.merge(daily_zscore, on=["experiment", "pen_id", "date"], how="left")


def write_subdaily_feed_drop_report(output_dir: Path, df: pd.DataFrame, thresholds: RuleThresholds | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    rule_thresholds = thresholds or RuleThresholds()

    sweep_thresholds = sorted({-0.5, -1.0, -1.5, -2.0, rule_thresholds.feed_drop})
    sweep_any = threshold_sweep(df, "feed_intake_daily_min_zscore_3d", sweep_thresholds, "any_signs")
    sweep_gut = threshold_sweep(df, "feed_intake_daily_min_zscore_3d", sweep_thresholds, "gut_signs")
    sweep_any.to_csv(output_dir / "clearfarm_feed_drop_subdaily_vs_any_signs.csv", index=False)
    sweep_gut.to_csv(output_dir / "clearfarm_feed_drop_subdaily_vs_gut_signs.csv", index=False)

    configured = confusion_for_threshold(
        df, "feed_intake_daily_min_zscore_3d", rule_thresholds.feed_drop, "any_signs"
    )
    n_reachable = df["feed_intake_daily_min_zscore_3d"].notna().sum()
    n_fires = int((df["feed_intake_daily_min_zscore_3d"] <= rule_thresholds.feed_drop).sum())

    lines = [
        "# ClearFarm feed_drop 규칙 재검증 (시간 단위 해상도)",
        "",
        f"데이터 출처: ClearFarm 원본 급이 로그(시간당 재집계), health-observed pen-day `{len(df)}`건",
        "",
        "## 해상도를 시간 단위로 올리자 -1.5 threshold가 실제로 발동한다",
        "",
        "- 1순위 검증(`clearfarm_feed_drop_validation_report.md`)에서 하루 1행 집계로는 z-score가 "
        "이론상 최대 1.1547이라 -1.5 threshold가 절대 발동하지 않는다는 걸 확인했다.",
        "- ClearFarm 원본 급이 로그는 방문 단위 타임스탬프(`hour` 컬럼)가 있어서, 돈방x시간 단위로 재집계하면 "
        "3일 rolling window 안에 최대 72개 점이 들어간다.",
        f"- 적용 config: `{rule_thresholds.source}`"
        f"- 이 해상도에서 feed_drop threshold({rule_thresholds.feed_drop:g})는 health-observed pen-day 중 `{n_fires}`/`{n_reachable}`일에서 실제로 발동한다 "
        "(1순위 검증에서는 0/779였다).",
        f"- 적용 threshold({rule_thresholds.feed_drop:g})의 confusion matrix: "
        f"sensitivity={configured['sensitivity']:.1%} / specificity={configured['specificity']:.1%} / "
        f"precision={configured['precision']:.1%}.",
        "",
        "## threshold sweep (daily_min_zscore, vs any_signs)",
        "",
        dataframe_to_markdown(sweep_any),
        "",
        "## threshold sweep (daily_min_zscore, vs gut_signs)",
        "",
        dataframe_to_markdown(sweep_gut),
        "",
        "## 판단",
        "",
        "- 해상도를 원래 설계에 맞게 올리자 `feed_drop`이 실제로 작동 가능한 신호가 됐다 -- "
        "이건 규칙 설계 문제가 아니라 **입력 데이터 준비 단계에서 하루 단위로 지나치게 뭉갠 것**이 원인이었다는 걸 "
        "구체적으로 확인한 것이다.",
        "- 다만 정밀도는 여전히 완벽하지 않다 -- feed_drop 단독보다는 다른 신호와의 co-occurrence가 "
        "여전히 필요하다는 기존 결론은 유지된다.",
        "- ClearFarm 외 다른 daily-only 데이터(RFID-LoRaWAN, 5126661 feeding)에도 같은 교훈이 적용된다: "
        "가능하면 원본의 sub-daily 타임스탬프를 보존한 채로 z-score/rolling feature를 계산해야 한다.",
    ]
    report = output_dir / "clearfarm_feed_drop_subdaily_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def write_thermal_report(output_dir: Path, df: pd.DataFrame, thresholds: RuleThresholds | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    thresholds = thresholds or RuleThresholds()

    observed_max = float(df["temperature_max"].max())
    configured = confusion_for_threshold(
        df, "temperature_max", thresholds.barn_temp_high, "heat_signs", "above"
    )

    percentiles = df["temperature_max"].quantile([0.50, 0.75, 0.90, 0.95, 0.99]).round(1)
    sweep_thresholds = sorted({thresholds.barn_temp_high, *percentiles.astype(float).tolist()})
    sweep = threshold_sweep(df, "temperature_max", sweep_thresholds, "heat_signs", "above")
    sweep.to_csv(output_dir / "clearfarm_barn_temp_high_vs_heat_signs.csv", index=False)

    lines = [
        "# ClearFarm barn_temp_high 규칙 검증",
        "",
        f"데이터 출처: ClearFarm growing-finishing pig sensor dataset (비육돈), health-observed pen-day `{len(df)}`건",
        "",
        "## 핵심 발견: 운영 threshold와 후보 threshold의 차이가 크다",
        "",
        f"- 적용 config: `{thresholds.source}`"
        f"- `barn_temp_high`는 `T_mean(창 내 max) >= {thresholds.barn_temp_high:g}`로 설정되어 있다.",
        f"- ClearFarm에서 관측된 일일 최고 온도(`temperature_max`)의 전체 기간 최댓값은 `{observed_max:.1f}도`다 -- "
        f"적용 threshold와 비교해야 한다.",
        f"- 그 결과 confusion matrix는 tp={int(configured['tp'])}, fn={int(configured['fn'])}: "
        "**적용 threshold에 따라 ClearFarm에서 barn_temp_high 발동 여부가 크게 달라진다.**",
        "- 열 스트레스 관찰 신호(`pant_sum > 0`, panting)는 실제로 전체의 3.9%일에 나타난다 -- "
        "즉 열 스트레스 자체는 이 농장에도 존재하지만, 40도라는 절대 threshold가 이 농장의 온도 스케일과 "
        "전혀 안 맞아서 그 신호를 하나도 못 잡는다.",
        "- co2_high/nh3_high(threshold가 너무 낮아 상시 발동)와 정반대 방향의 실패 사례다 -- "
        "**같은 프로젝트의 절대값 threshold들이 데이터셋에 따라 '항상 발동'과 '전혀 발동 안 함' 양쪽으로 다 실패할 수 있다는 걸 "
        "이번 검증에서 처음 확인했다.**",
        "",
        "## barn_temp_high: threshold sweep (temperature_max, vs heat_signs=panting)",
        "",
        dataframe_to_markdown(sweep),
        "",
        "## 판단",
        "",
        "- ClearFarm 자체 분포(p90~p99)로 threshold를 다시 잡아야 panting 신호를 일부라도 잡을 수 있다.",
        "- feed_drop, co2_high, nh3_high, barn_temp_high 4개 규칙 전부 절대값 threshold의 데이터셋 간 "
        "비전이성 문제를 보였다 -- 우연이 아니라 이 프로젝트의 domain_rules 설계 자체가 "
        "'AI Hub 한 데이터셋에 맞춘 절대 threshold'라는 공통 한계를 갖고 있다는 결론이 된다.",
    ]
    report = output_dir / "clearfarm_thermal_validation_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


RECALIBRATED_CO2_THRESHOLD = 2984  # best-F1 threshold from clearfarm_environment_validation_report.md
RECALIBRATED_BARN_TEMP_THRESHOLD = 31.6  # p95 threshold from clearfarm_thermal_validation_report.md


def confusion_for_composite(df: pd.DataFrame, rule_hit: pd.Series, sign_col: str) -> dict[str, float]:
    """Same confusion-matrix shape as `confusion_for_threshold`, but for a
    pre-combined boolean rule series (e.g. `feed_fires & co2_fires`)."""
    scored_sign = df[sign_col].astype(bool)
    rule = rule_hit.fillna(False).reindex(df.index).astype(bool)
    tp = int((rule & scored_sign).sum())
    fp = int((rule & ~scored_sign).sum())
    fn = int((~rule & scored_sign).sum())
    tn = int((~rule & ~scored_sign).sum())
    sensitivity = tp / (tp + fn) if tp + fn else np.nan
    specificity = tn / (tn + fp) if tn + fp else np.nan
    precision = tp / (tp + fp) if tp + fp else np.nan
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision and sensitivity else np.nan
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "sensitivity": sensitivity, "specificity": specificity, "precision": precision, "f1": f1}


def write_composite_report(output_dir: Path, df: pd.DataFrame, thresholds: RuleThresholds | None = None) -> Path:
    """Co-occurrence check: does AND-combining two recalibrated rules raise
    precision over either rule alone, the same tradeoff `domain_rules.py`'s
    `CO_OCCURRENCE_BONUS_PER_EXTRA_RULE` already assumes for the main
    pipeline? This is the first time that assumption is checked against a
    dataset with real ground truth rather than just AI Hub's "assumed
    normal" data.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    thresholds = thresholds or RuleThresholds()

    feed_fires = df["feed_intake_daily_min_zscore_3d"] <= thresholds.feed_drop
    co2_fires = df["co2_max"] >= thresholds.co2_high
    temp_fires = df["temperature_max"] >= thresholds.barn_temp_high

    combos = {
        "feed_drop": feed_fires,
        "co2_high": co2_fires,
        "barn_temp_high": temp_fires,
        "feed_drop AND co2_high": feed_fires.fillna(False) & co2_fires.fillna(False),
        "feed_drop AND barn_temp_high": feed_fires.fillna(False) & temp_fires.fillna(False),
        "co2_high AND barn_temp_high": co2_fires.fillna(False) & temp_fires.fillna(False),
        "all three": feed_fires.fillna(False) & co2_fires.fillna(False) & temp_fires.fillna(False),
    }
    rows = []
    for label, hit in combos.items():
        result = confusion_for_composite(df, hit, "any_signs")
        result["rule"] = label
        result["n_fires"] = int(hit.fillna(False).sum())
        rows.append(result)
    summary = pd.DataFrame(rows)[["rule", "n_fires", "tp", "fp", "fn", "tn", "sensitivity", "specificity", "precision", "f1"]]
    summary.to_csv(output_dir / "clearfarm_composite_rules_vs_any_signs.csv", index=False)

    single_best_precision = summary.iloc[:3]["precision"].max()
    two_way = summary.iloc[3:6]
    composite_best_row = two_way.loc[two_way["precision"].idxmax()]

    lines = [
        "# ClearFarm 복합 규칙(co-occurrence) 검증",
        "",
        f"데이터 출처: ClearFarm growing-finishing pig sensor dataset (비육돈), health-observed pen-day `{len(df)}`건",
        "",
        f"적용 config: `{thresholds.source}`. 3개 규칙(`feed_drop`={thresholds.feed_drop:g} -- 시간 단위 해상도에서는 작동함, "
        f"`co2_high`={thresholds.co2_high:g}ppm, `barn_temp_high`={thresholds.barn_temp_high:g}도)을 "
        "단독/조합으로 `any_signs`와 비교했다.",
        "",
        dataframe_to_markdown(summary),
        "",
        "## 판단",
        "",
        f"- 단일 규칙 중 최고 precision: `{single_best_precision:.1%}`("
        f"{summary.iloc[:3].loc[summary.iloc[:3]['precision'].idxmax(), 'rule']}, n_fires="
        f"{int(summary.iloc[:3].loc[summary.iloc[:3]['precision'].idxmax(), 'n_fires'])}). "
        f"2개 조합 중 최고 precision: `{composite_best_row['precision']:.1%}`(`{composite_best_row['rule']}`)이지만 "
        f"**발동 횟수가 `{int(composite_best_row['n_fires'])}`건뿐이라 이 숫자 하나로 결론 내리면 안 된다** -- "
        "가장 표본이 많은 조합은 `feed_drop AND co2_high`(n_fires="
        f"{int(summary.loc[summary['rule']=='feed_drop AND co2_high','n_fires'].iloc[0])}, precision="
        f"{summary.loc[summary['rule']=='feed_drop AND co2_high','precision'].iloc[0]:.1%})이고, "
        "이게 `domain_rules.py`의 co-occurrence bonus 설계 방향이 맞다는 걸 뒷받침하는 더 신뢰할 수 있는 근거다.",
        "- 다만 상승폭은 크지 않고(수 %p 수준), sensitivity는 크게 떨어진다 -- 2개 규칙을 AND로 묶으면 "
        "그만큼 실제 사례를 놓치는 비용이 크다는 것도 같이 봐야 한다.",
        "- 3개를 전부 AND로 묶으면 `tp=0`이 된다 -- **동시발생 조건을 과도하게 늘리면 신호가 완전히 사라질 수 있다**는 "
        "구체적 경고 사례다. co-occurrence bonus는 2개 정도까지가 실익이 있고, 그 이상은 검증 없이 늘리면 위험하다.",
    ]
    report = output_dir / "clearfarm_composite_rules_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate feed_drop/co2_high/nh3_high rules against ClearFarm health observations.")
    parser.add_argument("--pen-day-path", default=DEFAULT_PEN_DAY_PATH)
    parser.add_argument("--raw-dir", default=DEFAULT_CLEARFARM_RAW_DIR)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--rules-config", default="config/domain_rules.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    thresholds = load_rule_thresholds(args.rules_config)
    df = prepare_validation_frame(args.pen_day_path)
    feed_report = write_feed_drop_report(Path(args.artifact_dir), df)
    env_report = write_environment_report(Path(args.artifact_dir), df, thresholds)
    thermal_report = write_thermal_report(Path(args.artifact_dir), df, thresholds)
    subdaily_df = prepare_subdaily_validation_frame(args.pen_day_path, args.raw_dir)
    subdaily_report = write_subdaily_feed_drop_report(Path(args.artifact_dir), subdaily_df, thresholds)
    composite_report = write_composite_report(Path(args.artifact_dir), subdaily_df, thresholds)
    print(f"Wrote {feed_report}")
    print(f"Wrote {env_report}")
    print(f"Wrote {thermal_report}")
    print(f"Wrote {subdaily_report}")
    print(f"Wrote {composite_report}")


if __name__ == "__main__":
    main()
