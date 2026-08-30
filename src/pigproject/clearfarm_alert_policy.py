"""Apply a 3-level operational alert policy to ClearFarm rule scores."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.activity_model_dataset import dataframe_to_markdown


DEFAULT_SCORED_PATH = "artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_scored_pen_days.csv"
DEFAULT_OUTPUT_DIR = "artifacts/clearfarm_alert_policy/clearfarm_config"

OBSERVE_THRESHOLD = 0.3
CAUTION_THRESHOLD = 0.6
CCTV_THRESHOLD = 0.9
HEAT_CCTV_THRESHOLD = 0.9


def assign_policy_level(row: pd.Series) -> tuple[int, str, str]:
    rule_score = float(row.get("rule_score", 0.0) or 0.0)
    environment_score = float(row.get("environment_score", 0.0) or 0.0)
    reasons = str(row.get("rule_reasons", "") or "")

    if rule_score >= CCTV_THRESHOLD or environment_score >= HEAT_CCTV_THRESHOLD:
        if "barn_temp_high" in reasons or environment_score >= HEAT_CCTV_THRESHOLD:
            return 1, "cctv_focus", "CCTV 집중 확인 + 환경/고온 설비 점검"
        return 1, "cctv_focus", "CCTV 집중 확인 + 돈방 상태 현장 확인"
    if rule_score >= CAUTION_THRESHOLD:
        return 2, "caution", "다음 점검 순번 상향 + 사료/환경 추세 재확인"
    if rule_score >= OBSERVE_THRESHOLD:
        return 3, "observe", "관찰 목록 등록 + 다음 window에서 지속 여부 확인"
    return 4, "normal", "알림 없음"


def apply_alert_policy(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
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
        "experiment",
        "pen_id",
        "date",
        "rule_score",
        "management_score",
        "environment_score",
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
        "- `caution`은 관리자가 점검 순번을 올려야 하는 단계다. 사료 섭취 저하와 환경 신호가 같이 있는지 본다.",
        "- `cctv_focus`는 CCTV/YOLO 분석을 요청하는 단계다. 돈방 단위 후보를 개별 돼지 관찰로 내려보낸다.",
        "- 이 정책은 ClearFarm 외부 검증용이며, 메인 운영 config에 반영하려면 농장별 threshold 자동 선택 단계가 필요하다.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return policy_path, summary_path, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a 3-level alert policy to ClearFarm scored pen-days.")
    parser.add_argument("--scored-path", default=DEFAULT_SCORED_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scored = pd.read_csv(args.scored_path, low_memory=False)
    policy = apply_alert_policy(scored)
    policy_path, summary_path, report_path = write_policy_outputs(policy, args.output_dir)
    print(f"policy: {policy_path}")
    print(f"summary: {summary_path}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
