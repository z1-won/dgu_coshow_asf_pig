"""Create candidate domain-rule configs without changing the production config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from pigproject.bioenergy_report import dataframe_to_markdown

DEFAULT_OVERRIDES = {"co2_high": 1100}


def build_candidate_config(config: dict, overrides: dict[str, float]) -> tuple[dict, pd.DataFrame]:
    candidate = json.loads(json.dumps(config, ensure_ascii=False))
    rows = []
    for rule in candidate.get("rules", []):
        rule_id = str(rule.get("id", ""))
        if rule_id not in overrides:
            continue
        old_threshold = rule.get("threshold")
        rule["threshold"] = overrides[rule_id]
        note = str(rule.get("note", ""))
        suffix = f" Candidate override: threshold {old_threshold} -> {overrides[rule_id]}."
        if suffix not in note:
            rule["note"] = (note + suffix).strip()
        rows.append(
            {
                "rule_id": rule_id,
                "category": rule.get("category", ""),
                "feature": rule.get("feature", ""),
                "op": rule.get("op", ""),
                "old_threshold": old_threshold,
                "candidate_threshold": overrides[rule_id],
            }
        )
    missing = sorted(set(overrides) - {row["rule_id"] for row in rows})
    if missing:
        raise ValueError(f"Unknown rule ids for threshold override: {missing}")
    return candidate, pd.DataFrame(rows)


def write_candidate_outputs(
    candidate_config: dict,
    changes: pd.DataFrame,
    config_output: str | Path,
    changes_output: str | Path,
    report_output: str | Path,
) -> tuple[Path, Path, Path]:
    config_path = Path(config_output)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(candidate_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    changes_path = Path(changes_output)
    changes_path.parent.mkdir(parents=True, exist_ok=True)
    changes.to_csv(changes_path, index=False)

    report_path = Path(report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Candidate Rule Config 리포트",
        "",
        "## 목적",
        "",
        "운영 config를 직접 수정하지 않고 threshold 후보 config를 별도로 생성한다.",
        "",
        "## 변경 후보",
        "",
        dataframe_to_markdown(changes) if len(changes) else "변경 없음.",
        "",
        "## 사용 기준",
        "",
        "- 이 파일은 실험용 후보 config다.",
        "- 실제 `config/domain_rules.json` 반영 전에는 lead-time, precision, recall 비교를 다시 확인한다.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path, changes_path, report_path


def parse_overrides(raw: str) -> dict[str, float]:
    if not raw.strip():
        return dict(DEFAULT_OVERRIDES)
    overrides: dict[str, float] = {}
    for part in raw.split(","):
        if not part.strip():
            continue
        key, value = part.split("=", 1)
        overrides[key.strip()] = float(value.strip())
    return overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a candidate domain-rule config with threshold overrides.")
    parser.add_argument("--base-config", default="config/domain_rules.json")
    parser.add_argument("--overrides", default="co2_high=1100")
    parser.add_argument("--output-config", default="config/domain_rules_candidate_co2_1100.json")
    parser.add_argument("--changes-output", default="artifacts/rule_candidate_config_changes.csv")
    parser.add_argument("--report", default="artifacts/rule_candidate_config_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_config = json.loads(Path(args.base_config).read_text(encoding="utf-8"))
    candidate, changes = build_candidate_config(base_config, parse_overrides(args.overrides))
    config_path, changes_path, report_path = write_candidate_outputs(
        candidate,
        changes,
        args.output_config,
        args.changes_output,
        args.report,
    )
    print(f"candidate_config: {config_path}")
    print(f"changes: {changes_path}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
