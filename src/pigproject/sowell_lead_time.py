"""Build SOWELL event mappings and lead-time evaluation frames."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

DEFAULT_EVENT_LINKAGE = "artifacts/external/sowell_event_linkage/sowell_event_signal_linkage.csv"
DEFAULT_GROUP_DAY_SIGNALS = "artifacts/external/sowell_event_linkage/sowell_group_day_signals.csv"
DEFAULT_OUTPUT_DIR = "artifacts/external/sowell_lead_time"
DEFAULT_HORIZONS = (24, 48, 72)

EVENT_KIND_MAP = {
    "hot_thermic_conditions": ("environment_heat", "target", "고온 환경 스트레스"),
    "control_week_hot_thermic_conditions": ("environment_heat", "control", "고온 통제/비교 구간"),
    "cold_thermic_conditions": ("environment_cold", "target", "저온 환경 스트레스"),
    "control_week_cold_thermic_conditions": ("environment_cold", "control", "저온 통제/비교 구간"),
    "feed_competition": ("feed_competition", "target", "급이 경쟁 이벤트"),
    "control_week_feed_competition": ("feed_competition", "control", "급이 경쟁 통제/비교 구간"),
    "sound_event": ("sound_stress", "target", "음향 스트레스 이벤트"),
    "control_week_sound_event": ("sound_stress", "control", "음향 통제/비교 구간"),
    "hierarchy": ("social_hierarchy", "target", "서열 형성/사회적 스트레스 후보"),
    "Impoverishment_pen": ("pen_enrichment", "target", "빈약한 돈방 환경 이벤트"),
    "control_week_poor_pen": ("pen_enrichment", "control", "빈약한 돈방 통제/비교 구간"),
    "enrichment_toy": ("enrichment", "context", "장난감 풍부화 구간"),
    "control_week_enrichment_toy": ("enrichment", "control", "장난감 풍부화 통제/비교 구간"),
    "enrichment_straw": ("enrichment", "context", "깔짚 풍부화 구간"),
    "control_week_enrichment_straw": ("enrichment", "control", "깔짚 풍부화 통제/비교 구간"),
}

TARGET_CATEGORY_TO_ALERT = {
    "environment_heat": "heat_alert",
    "environment_cold": "cold_alert",
    "feed_competition": "feed_attention",
    "sound_stress": "sound_attention",
    "social_hierarchy": "activity_attention",
    "pen_enrichment": "activity_attention",
    "enrichment": "activity_attention",
}


def map_event_kind(kind: str) -> tuple[str, str, str]:
    return EVENT_KIND_MAP.get(kind, ("other", "context", "미분류 이벤트"))


def add_event_mapping(events: pd.DataFrame) -> pd.DataFrame:
    mapped = events.copy()
    triples = mapped["Kind_event"].map(map_event_kind)
    mapped["project_category"] = triples.map(lambda x: x[0])
    mapped["event_role"] = triples.map(lambda x: x[1])
    mapped["korean_label"] = triples.map(lambda x: x[2])
    mapped["include_in_recall"] = mapped["event_role"].eq("target")
    mapped["target_alert"] = mapped["project_category"].map(TARGET_CATEGORY_TO_ALERT).fillna("any_alert")
    return mapped


def _robust_stats(df: pd.DataFrame, signal: str) -> pd.DataFrame:
    q = df.groupby("ID_group")[signal].quantile([0.25, 0.5, 0.75]).unstack()
    q.columns = ["q25", "median", "q75"]
    q["iqr"] = (q["q75"] - q["q25"]).replace(0, np.nan)
    return q.reset_index().rename(columns={"median": f"{signal}_median", "iqr": f"{signal}_iqr"})


def add_daily_scores(group_day: pd.DataFrame) -> pd.DataFrame:
    daily = group_day.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    numeric_cols = [
        "feed_kg_per_sow",
        "water_l_per_sow",
        "moving_time_mean",
        "air_temp_mean",
        "air_temp_max",
    ]
    for col in numeric_cols:
        if col in daily:
            daily[col] = pd.to_numeric(daily[col], errors="coerce")

    for signal in numeric_cols:
        if signal not in daily:
            continue
        stats = _robust_stats(daily, signal)
        daily = daily.merge(stats[["ID_group", f"{signal}_median", f"{signal}_iqr"]], on="ID_group", how="left")

    eps = 1e-9
    daily["feed_drop_score"] = (
        (daily["feed_kg_per_sow_median"] - daily["feed_kg_per_sow"]) / (daily["feed_kg_per_sow_iqr"].fillna(0) + eps)
    ).clip(lower=0)
    daily["water_spike_score"] = (
        (daily["water_l_per_sow"] - daily["water_l_per_sow_median"]) / (daily["water_l_per_sow_iqr"].fillna(0) + eps)
    ).clip(lower=0)
    daily["activity_drop_score"] = (
        (daily["moving_time_mean_median"] - daily["moving_time_mean"]) / (daily["moving_time_mean_iqr"].fillna(0) + eps)
    ).clip(lower=0)
    daily["heat_score"] = (
        (daily["air_temp_mean"] - daily["air_temp_mean_median"]) / (daily["air_temp_mean_iqr"].fillna(0) + eps)
    ).clip(lower=0)
    daily["cold_score"] = (
        (daily["air_temp_mean_median"] - daily["air_temp_mean"]) / (daily["air_temp_mean_iqr"].fillna(0) + eps)
    ).clip(lower=0)

    daily["feed_attention"] = daily["feed_drop_score"] >= 1.5
    daily["water_attention"] = daily["water_spike_score"] >= 1.5
    daily["activity_attention"] = daily["activity_drop_score"] >= 1.5
    daily["heat_alert"] = (daily["heat_score"] >= 1.5) | (daily["air_temp_mean"] >= 27.0)
    daily["cold_alert"] = (daily["cold_score"] >= 1.5) | (daily["air_temp_mean"] <= 17.0)
    daily["sound_attention"] = daily["activity_attention"] | daily["water_attention"]
    alert_cols = ["feed_attention", "water_attention", "activity_attention", "heat_alert", "cold_alert", "sound_attention"]
    daily["any_alert"] = daily[alert_cols].any(axis=1)
    daily["alert_reasons"] = daily[alert_cols].apply(lambda r: ", ".join([c for c, v in r.items() if bool(v)]), axis=1)
    return daily


def build_event_detection_frame(
    events: pd.DataFrame,
    daily_scores: pd.DataFrame,
    horizons_hours: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    mapped = add_event_mapping(events)
    mapped["begin_dt"] = pd.to_datetime(mapped["begin_dt"], errors="coerce")
    mapped["end_dt"] = pd.to_datetime(mapped["end_dt"], errors="coerce")
    rows = []
    for _, ev in mapped.iterrows():
        if pd.isna(ev["begin_dt"]) or pd.isna(ev["end_dt"]):
            continue
        group = ev["ID_group"]
        group_daily = daily_scores[daily_scores["ID_group"].eq(group)].copy()
        target_alert = ev["target_alert"] if ev["target_alert"] in group_daily.columns else "any_alert"
        during = group_daily[(group_daily["date"] >= ev["begin_dt"].normalize()) & (group_daily["date"] <= ev["end_dt"].normalize())]
        during_hit = bool(during[target_alert].fillna(False).any()) if not during.empty else False
        row = {
            "ID_event": ev["ID_event"],
            "ID_group": group,
            "Kind_event": ev["Kind_event"],
            "project_category": ev["project_category"],
            "event_role": ev["event_role"],
            "korean_label": ev["korean_label"],
            "include_in_recall": bool(ev["include_in_recall"]),
            "target_alert": target_alert,
            "begin_dt": ev["begin_dt"],
            "end_dt": ev["end_dt"],
            "during_days": len(during),
            "during_detected": during_hit,
            "during_alert_reasons": "; ".join(during.loc[during[target_alert].fillna(False), "alert_reasons"].dropna().unique()[:5]),
        }
        for hours in horizons_hours:
            start = ev["begin_dt"] - pd.Timedelta(hours=hours)
            pre = group_daily[(group_daily["date"] >= start.normalize()) & (group_daily["date"] < ev["begin_dt"].normalize())]
            hit = bool(pre[target_alert].fillna(False).any()) if not pre.empty else False
            row[f"pre_{hours}h_days"] = len(pre)
            row[f"pre_{hours}h_detected"] = hit
            row[f"pre_{hours}h_alert_reasons"] = "; ".join(pre.loc[pre[target_alert].fillna(False), "alert_reasons"].dropna().unique()[:5])
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_detection(events: pd.DataFrame, horizons_hours: tuple[int, ...] = DEFAULT_HORIZONS) -> pd.DataFrame:
    target = events[events["include_in_recall"]].copy()
    rows = []
    scopes = [("all_targets", target)] + [(cat, g) for cat, g in target.groupby("project_category")]
    for scope, frame in scopes:
        if frame.empty:
            continue
        row = {
            "scope": scope,
            "events": len(frame),
            "during_detected": int(frame["during_detected"].sum()),
            "during_recall": float(frame["during_detected"].mean()),
        }
        for hours in horizons_hours:
            col = f"pre_{hours}h_detected"
            row[f"pre_{hours}h_detected"] = int(frame[col].sum())
            row[f"pre_{hours}h_recall"] = float(frame[col].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def _pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value * 100:.1f}%"


def write_report(mapped_events: pd.DataFrame, scored_daily: pd.DataFrame, event_frame: pd.DataFrame, summary: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    mapped_events.to_csv(output_dir / "sowell_event_category_map.csv", index=False)
    scored_daily.to_csv(output_dir / "sowell_group_day_rule_scores.csv", index=False)
    event_frame.to_csv(output_dir / "sowell_lead_time_event_frame.csv", index=False)
    summary.to_csv(output_dir / "sowell_lead_time_summary.csv", index=False)

    display = summary.copy()
    for col in display.columns:
        if col.endswith("recall"):
            display[col] = display[col].map(_pct)
    lines = [
        "# SOWELL Lead-Time 평가 프레임",
        "",
        "## 핵심 요약",
        "",
        dataframe_to_markdown(display),
        "",
        "## 해석",
        "",
        "- SOWELL은 실험 이벤트 데이터라서 이벤트 시작 전 사전 포착률은 최종 농장 성능으로 주장하지 않는다.",
        "- `during_recall`은 이벤트가 진행되는 동안 해당 센서 변화가 포착되는지 보는 외부 검증 수치다.",
        "- `pre_24h/48h/72h_recall`은 자연 발생 조기경보가 아니라, 이벤트 전 window에서 이미 같은 종류의 이상 신호가 있었는지 확인하는 보조 수치다.",
        "- 고온/저온 이벤트는 환경 센서 변화가 분명하므로 현재 프로젝트의 환경 이상 규칙 보강에 우선 사용한다.",
        "",
        "## 다음 작업",
        "",
        "1. SOWELL summary를 기존 external validation summary에 추가한다.",
        "2. 고온/저온 threshold 후보를 ClearFarm/HotPig 결과와 비교한다.",
        "3. feed/activity 계열은 threshold를 바로 올리지 말고 오탐 부담을 같이 계산한다.",
    ]
    report_path = output_dir / "sowell_lead_time_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def build_sowell_lead_time(
    event_linkage_path: str | Path = DEFAULT_EVENT_LINKAGE,
    group_day_path: str | Path = DEFAULT_GROUP_DAY_SIGNALS,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    horizons_hours: tuple[int, ...] = DEFAULT_HORIZONS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, Path]:
    events = pd.read_csv(event_linkage_path)
    daily = pd.read_csv(group_day_path)
    mapped_events = add_event_mapping(events)
    scored_daily = add_daily_scores(daily)
    event_frame = build_event_detection_frame(mapped_events, scored_daily, horizons_hours=horizons_hours)
    summary = summarize_detection(event_frame, horizons_hours=horizons_hours)
    report_path = write_report(mapped_events, scored_daily, event_frame, summary, Path(output_dir))
    return mapped_events, scored_daily, event_frame, summary, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SOWELL event category and lead-time evaluation frames.")
    parser.add_argument("--event-linkage", default=DEFAULT_EVENT_LINKAGE)
    parser.add_argument("--group-day", default=DEFAULT_GROUP_DAY_SIGNALS)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--lead-hours", default="24,48,72")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    horizons = tuple(int(v.strip()) for v in args.lead_hours.split(",") if v.strip())
    _, _, _, summary, report_path = build_sowell_lead_time(
        event_linkage_path=args.event_linkage,
        group_day_path=args.group_day,
        output_dir=args.output_dir,
        horizons_hours=horizons,
    )
    print(f"report: {report_path}")
    print(dataframe_to_markdown(summary))


if __name__ == "__main__":
    main()
