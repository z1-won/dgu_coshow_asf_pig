"""Convert ClearFarm 3-level policy output into the common action-queue schema."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pigproject.action_queue_report import build_action_queue, build_incident_queue, write_action_queues
from pigproject.action_queue_report import write_incident_queue, write_report
from pigproject.activity_model_dataset import dataframe_to_markdown


DEFAULT_POLICY_PATH = "artifacts/clearfarm_alert_policy/clearfarm_config/clearfarm_3level_alert_policy.csv"
DEFAULT_OUTPUT_CSV = "data/processed/external/clearfarm/clearfarm_action_queue_input.csv"
DEFAULT_ACTION_QUEUE_DIR = "artifacts/clearfarm_action_queue/clearfarm_config"


def categories_from_reasons(reasons: object) -> str:
    tokens = {part.strip() for part in str(reasons or "").split(",") if part.strip()}
    categories: list[str] = []
    if "feed_drop" in tokens:
        categories.append("management")
    if tokens & {"co2_high", "nh3_high", "barn_temp_high"}:
        categories.append("environment")
    return ",".join(categories)


def tier_from_policy(policy_level: object) -> str:
    level = str(policy_level or "")
    if level == "cctv_focus":
        return "high"
    if level == "caution":
        return "medium"
    if level == "observe":
        return "watch"
    return "normal"


def reason_from_row(row: pd.Series) -> str:
    categories = categories_from_reasons(row.get("rule_reasons", ""))
    parts: list[str] = []
    if "management" in categories:
        management_reasons = [token for token in str(row.get("rule_reasons", "")).split(",") if token == "feed_drop"]
        if management_reasons:
            parts.append("management: " + ",".join(management_reasons))
    if "environment" in categories:
        env_tokens = [
            token
            for token in str(row.get("rule_reasons", "")).split(",")
            if token in {"co2_high", "nh3_high", "barn_temp_high"}
        ]
        if env_tokens:
            parts.append("environment: " + ",".join(env_tokens))
    base = " | ".join(parts)
    if not base:
        return ""
    return f"policy:{row.get('policy_level', '')} rule: {base}"


def adapt_policy_to_action_input(policy: pd.DataFrame) -> pd.DataFrame:
    frame = policy.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["alert_category"] = frame["rule_reasons"].apply(categories_from_reasons)
    frame["tier"] = frame["policy_level"].apply(tier_from_policy)
    frame["reason"] = frame.apply(reason_from_row, axis=1)
    frame["track"] = "clearfarm_rule_policy"
    frame["source_dataset"] = "ClearFarm"
    frame["chamber_id"] = (
        "clearfarm:exp" + frame["experiment"].astype(str) + ":pen" + frame["pen_id"].astype(str)
    )
    frame["start_datetime"] = frame["date"]
    frame["end_datetime"] = frame["date"] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    frame["track_score"] = frame["rule_score"]
    frame["model_component"] = 0.0
    frame["rule_component"] = frame["rule_score"]
    frame["model_anomaly"] = False
    frame["rule_anomaly"] = frame["policy_level"].isin(["caution", "cctv_focus"])
    frame["final_alert"] = frame["rule_anomaly"]

    columns = [
        "track",
        "source_dataset",
        "chamber_id",
        "start_datetime",
        "end_datetime",
        "model_component",
        "rule_component",
        "track_score",
        "management_score",
        "environment_score",
        "alert_category",
        "model_anomaly",
        "rule_anomaly",
        "final_alert",
        "operational_alert",
        "cctv_requested",
        "policy_level",
        "tier",
        "reason",
        "recommended_action",
    ]
    return frame[columns].sort_values(
        ["cctv_requested", "policy_level", "track_score", "environment_score", "management_score"],
        ascending=[False, True, False, False, False],
    ).reset_index(drop=True)


def write_adapter_report(action_input: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = action_input["policy_level"].value_counts()
    queue_ready = action_input[action_input["operational_alert"].astype(bool)]
    cctv = action_input[action_input["cctv_requested"].astype(bool)]
    lines = [
        "# ClearFarm Action Queue Adapter",
        "",
        "## 요약",
        "",
        f"- action queue 입력 행: `{len(action_input)}`",
        f"- operational alert: `{len(queue_ready)}`",
        f"- CCTV 요청 후보: `{len(cctv)}`",
        f"- cctv_focus: `{int(counts.get('cctv_focus', 0))}`",
        f"- caution: `{int(counts.get('caution', 0))}`",
        f"- observe: `{int(counts.get('observe', 0))}`",
        f"- normal: `{int(counts.get('normal', 0))}`",
        "",
        "## CCTV 요청 상위 20건",
        "",
        dataframe_to_markdown(
            cctv[
                [
                    "policy_level",
                    "chamber_id",
                    "start_datetime",
                    "track_score",
                    "management_score",
                    "environment_score",
                    "alert_category",
                    "reason",
                    "recommended_action",
                ]
            ].head(20)
        )
        if len(cctv)
        else "해당 없음.",
        "",
        "## 판단",
        "",
        "- 이 파일은 ClearFarm 전용 scorecard 결과를 메인 action queue 스키마로 맞춘 어댑터다.",
        "- `cctv_requested=True`인 행만 팀원 YOLO/CCTV 집중 분석 입력으로 넘기면 된다.",
        "- `observe`는 action queue에는 남지만 즉시 CCTV 요청은 하지 않는다.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def run_adapter(
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    output_csv: str | Path = DEFAULT_OUTPUT_CSV,
    action_queue_dir: str | Path = DEFAULT_ACTION_QUEUE_DIR,
) -> dict[str, Path]:
    policy = pd.read_csv(policy_path, low_memory=False)
    action_input = adapt_policy_to_action_input(policy)
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    action_input.to_csv(output, index=False)

    alerts = action_input[action_input["operational_alert"].astype(bool)].copy()
    queue = build_action_queue(alerts)
    incidents = build_incident_queue(queue)
    queue_paths = write_action_queues(queue, action_queue_dir)
    action_dir = Path(action_queue_dir)
    incident_path = write_incident_queue(incidents, action_dir / "incident_queue.csv")
    report_path = write_report(queue, action_dir / "action_queue_report.md", incident_queue=incidents)
    adapter_report = write_adapter_report(action_input, action_dir / "adapter_report.md")
    return {
        "action_input": output,
        "combined_queue": queue_paths["combined"],
        "management_queue": queue_paths["management"],
        "environment_queue": queue_paths["environment"],
        "incident_queue": incident_path,
        "action_report": report_path,
        "adapter_report": adapter_report,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert ClearFarm alert policy rows into action queue input.")
    parser.add_argument("--policy-path", default=DEFAULT_POLICY_PATH)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--action-queue-dir", default=DEFAULT_ACTION_QUEUE_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = run_adapter(args.policy_path, args.output_csv, args.action_queue_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
