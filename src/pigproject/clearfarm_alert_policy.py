"""Apply a 3-level operational alert policy to ClearFarm rule scores."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown
from pigproject.clearfarm_precision_tuning import build_policy_masks


DEFAULT_SCORED_PATH = "artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_scored_pen_days.csv"
DEFAULT_OUTPUT_DIR = "artifacts/clearfarm_alert_policy/clearfarm_config"
DEFAULT_PRECISION_FRAME_PATH = (
    "artifacts/clearfarm_precision_tuning/full_recall_candidate/clearfarm_precision_tuning_frame.csv"
)
DEFAULT_PRECISION_POLICY = "added_recent_same_reason_14d"

OBSERVE_THRESHOLD = 0.3
CAUTION_THRESHOLD = 0.6
CCTV_THRESHOLD = 0.9
HEAT_CCTV_THRESHOLD = 0.9
ENV_SCREENING_TEMP_C = 28.7
ENV_BALANCED_TEMP_C = 30.4
ENV_HIGH_CONFIDENCE_TEMP_C = 31.6


def assign_environment_policy(row: pd.Series) -> tuple[str, str, str]:
    temp = pd.to_numeric(row.get("temperature_max"), errors="coerce")
    if pd.isna(temp):
        return "not_available", "측정 없음", "온도 데이터 없음"
    if temp >= ENV_HIGH_CONFIDENCE_TEMP_C:
        return "high_confidence", "고확신", "CCTV/현장 확인 우선순위"
    if temp >= ENV_BALANCED_TEMP_C:
        return "balanced", "균형", "환경 이상 기본 기준 후보"
    if temp >= ENV_SCREENING_TEMP_C:
        return "screening", "선별", "관찰/추세 확인 후보"
    return "normal", "정상 범위", "온도 기준 이상 없음"


def attach_environment_policy(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    assigned = out.apply(assign_environment_policy, axis=1, result_type="expand")
    assigned.columns = ["environment_temp_policy", "environment_temp_label", "environment_temp_action"]
    return pd.concat([out, assigned], axis=1)


def assign_policy_level(row: pd.Series) -> tuple[int, str, str]:
    rule_score = float(row.get("rule_score", 0.0) or 0.0)
    environment_score = float(row.get("environment_score", 0.0) or 0.0)
    reasons = str(row.get("rule_reasons", "") or "")
    precision_confirmed = bool(row.get("precision_policy_alert", True))

    if rule_score >= OBSERVE_THRESHOLD and not precision_confirmed:
        return 3, "observe", "관찰 후보 유지 + 같은 원인 반복 여부 확인"

    if rule_score >= CCTV_THRESHOLD or environment_score >= HEAT_CCTV_THRESHOLD:
        if "barn_temp_high" in reasons or environment_score >= HEAT_CCTV_THRESHOLD:
            return 1, "cctv_focus", "CCTV 집중 확인 + 환경/고온 설비 점검"
        return 1, "cctv_focus", "CCTV 집중 확인 + 돈방 상태 현장 확인"
    if rule_score >= CAUTION_THRESHOLD:
        return 2, "caution", "다음 점검 순번 상향 + 사료/환경 추세 재확인"
    if rule_score >= OBSERVE_THRESHOLD:
        return 3, "observe", "관찰 목록 등록 + 다음 window에서 지속 여부 확인"
    return 4, "normal", "알림 없음"


def attach_precision_policy(
    scored: pd.DataFrame,
    precision_frame: pd.DataFrame,
    precision_policy: str = DEFAULT_PRECISION_POLICY,
) -> pd.DataFrame:
    out = scored.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["experiment"] = out["experiment"].astype(str)
    out["pen_id"] = out["pen_id"].astype(str)

    frame = precision_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["experiment"] = frame["experiment"].astype(str)
    frame["pen_id"] = frame["pen_id"].astype(str)
    masks = build_policy_masks(frame)
    if precision_policy not in masks:
        options = ", ".join(sorted(masks))
        raise ValueError(f"Unknown precision policy: {precision_policy}. Available: {options}")

    gate = frame[["experiment", "pen_id", "date", "baseline_alert", "candidate_alert", "added_alert"]].copy()
    gate["precision_policy"] = precision_policy
    gate["precision_policy_alert"] = masks[precision_policy].astype(bool).to_numpy()
    gate["precision_suppressed"] = gate["candidate_alert"] & ~gate["precision_policy_alert"]

    out = out.merge(gate, on=["experiment", "pen_id", "date"], how="left")
    out["precision_policy"] = out["precision_policy"].fillna("none")
    out["precision_policy_alert"] = out["precision_policy_alert"].fillna(True).astype(bool)
    out["precision_suppressed"] = out["precision_suppressed"].fillna(False).astype(bool)
    out["added_alert"] = out["added_alert"].fillna(False).astype(bool)
    return out


def apply_alert_policy(
    scored: pd.DataFrame,
    precision_frame: pd.DataFrame | None = None,
    precision_policy: str = DEFAULT_PRECISION_POLICY,
) -> pd.DataFrame:
    out = attach_environment_policy(scored)
    if precision_frame is not None:
        out = attach_precision_policy(out, precision_frame, precision_policy)
    else:
        out["precision_policy"] = "none"
        out["precision_policy_alert"] = True
        out["precision_suppressed"] = False
        out["added_alert"] = False
    assigned = out.apply(assign_policy_level, axis=1, result_type="expand")
    assigned.columns = ["policy_rank", "policy_level", "recommended_action"]
    out = pd.concat([out, assigned], axis=1)
    out["operational_alert"] = out["policy_level"] != "normal"
    out["cctv_requested"] = out["policy_level"] == "cctv_focus"
    return out.sort_values(
        ["policy_rank", "rule_score", "environment_score", "management_score", "date"],
        ascending=[True, False, False, False, True],
    ).reset_index(drop=True)


def summarize_policy(policy: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for level in ["cctv_focus", "caution", "observe", "normal"]:
        group = policy[policy["policy_level"] == level]
        if len(group) == 0:
            rows.append(
                {
                    "policy_level": level,
                    "n_pen_days": 0,
                    "precision_suppressed": 0,
                    "environment_screening_or_higher": 0,
                    "environment_balanced_or_higher": 0,
                    "environment_high_confidence": 0,
                    "any_signs_rate": 0.0,
                    "respiratory_signs_rate": 0.0,
                    "gut_signs_rate": 0.0,
                    "heat_signs_rate": 0.0,
                }
            )
            continue
        rows.append(
            {
                "policy_level": level,
                "n_pen_days": len(group),
                "precision_suppressed": int(group.get("precision_suppressed", pd.Series(False, index=group.index)).sum()),
                "environment_screening_or_higher": int(group.get("environment_temp_policy", pd.Series("normal", index=group.index)).isin(["screening", "balanced", "high_confidence"]).sum()),
                "environment_balanced_or_higher": int(group.get("environment_temp_policy", pd.Series("normal", index=group.index)).isin(["balanced", "high_confidence"]).sum()),
                "environment_high_confidence": int(group.get("environment_temp_policy", pd.Series("normal", index=group.index)).eq("high_confidence").sum()),
                "any_signs_rate": float(group["any_signs"].mean()),
                "respiratory_signs_rate": float(group["respiratory_signs"].mean()),
                "gut_signs_rate": float(group["gut_signs"].mean()),
                "heat_signs_rate": float(group["heat_signs"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _format_report_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["any_signs_rate", "respiratory_signs_rate", "gut_signs_rate", "heat_signs_rate"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: f"{value:.1%}")
    for col in ["rule_score", "feed_env_score", "management_score", "environment_score"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    return out


def write_policy_outputs(policy: pd.DataFrame, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    policy_path = output / "clearfarm_3level_alert_policy.csv"
    summary_path = output / "clearfarm_3level_alert_policy_summary.csv"
    report_path = output / "clearfarm_3level_alert_policy_report.md"

    summary = summarize_policy(policy)
    policy.to_csv(policy_path, index=False)
    summary.to_csv(summary_path, index=False)

    top_cols = [
        "policy_level",
        "precision_policy",
        "precision_suppressed",
        "experiment",
        "pen_id",
        "date",
        "rule_score",
        "management_score",
        "environment_score",
        "environment_temp_label",
        "environment_temp_action",
        "rule_reasons",
        "any_signs",
        "respiratory_signs",
        "gut_signs",
        "heat_signs",
        "recommended_action",
    ]
    top_alerts = policy[policy["operational_alert"]].head(30)[top_cols]

    lines = [
        "# ClearFarm 3단계 알림 정책",
        "",
        "## 정책 기준",
        "",
        f"- 관찰(observe): `rule_score >= {OBSERVE_THRESHOLD}`",
        f"- 주의(caution): `rule_score >= {CAUTION_THRESHOLD}`",
        f"- CCTV 집중 확인(cctv_focus): `rule_score >= {CCTV_THRESHOLD}` 또는 `environment_score >= {HEAT_CCTV_THRESHOLD}`",
        f"- 환경 온도 해석: 선별 `{ENV_SCREENING_TEMP_C}C`, 균형 `{ENV_BALANCED_TEMP_C}C`, 고확신 `{ENV_HIGH_CONFIDENCE_TEMP_C}C` 이상",
        "- 환경 온도 해석은 별도 컬럼으로 제공하며 기존 policy_level을 자동 승격하지 않는다.",
        "- precision filter 사용 시, 새 recall 후보가 필터를 통과하지 못하면 `observe`에 머문다.",
        "- 정상(normal): 위 조건에 해당하지 않음",
        "",
        "## 단계별 실제 라벨 비율",
        "",
        dataframe_to_markdown(_format_report_table(summary)),
        "",
        "## 상위 알림 30건",
        "",
        dataframe_to_markdown(_format_report_table(top_alerts)) if len(top_alerts) else "해당 없음.",
        "",
        "## 운영 해석",
        "",
        "- `observe`는 recall을 넓히는 조기 선별 단계다. 즉시 현장 출동보다 다음 window 지속 여부 확인에 가깝다.",
        "- precision filter가 붙은 `observe`는 버리는 알림이 아니라, 확정 알림으로 승격하지 않는 관찰 후보로 해석한다.",
        "- `caution`은 관리자가 점검 순번을 올려야 하는 단계다. 사료 섭취 저하와 환경 신호가 같이 있는지 본다.",
        "- `cctv_focus`는 CCTV/YOLO 분석을 요청하는 단계다. 돈방 단위 후보를 개별 돼지 관찰로 내려보낸다.",
        "- 환경 온도 단계는 성능 해석/검증용 보조 컬럼이다. 실제 운영 승격은 rule_score, environment_score, precision filter가 계속 담당한다.",
        "- 이 정책은 ClearFarm 외부 검증용이며, 메인 운영 config에 반영하려면 농장별 threshold 자동 선택 단계가 필요하다.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return policy_path, summary_path, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a 3-level alert policy to ClearFarm scored pen-days.")
    parser.add_argument("--scored-path", default=DEFAULT_SCORED_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--precision-frame", default=None)
    parser.add_argument("--precision-policy", default=DEFAULT_PRECISION_POLICY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scored = pd.read_csv(args.scored_path, low_memory=False)
    precision_frame = pd.read_csv(args.precision_frame, low_memory=False) if args.precision_frame else None
    policy = apply_alert_policy(scored, precision_frame=precision_frame, precision_policy=args.precision_policy)
    policy_path, summary_path, report_path = write_policy_outputs(policy, args.output_dir)
    print(f"policy: {policy_path}")
    print(f"summary: {summary_path}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
