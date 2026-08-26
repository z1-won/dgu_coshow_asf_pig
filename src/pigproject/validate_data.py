"""Data quality checks for normalized pig anomaly datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "chamber_number",
    "datetime",
    "T",
    "RH",
    "CO2",
    "NH3",
]

MODEL_COLUMNS = [
    "distance",
    "breath_rate",
    "rectal_temperature",
    "back_temperature",
    "neck_temperature",
    "head_temperature",
    "ventilation_rate",
    "feedstuff_volume",
    "watersupply",
]


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    table = df.reset_index()
    table.columns = [str(col) for col in table.columns]
    rows = ["| " + " | ".join(table.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(table.columns)) + " |")
    for _, row in table.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def validate_features(input_path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(input_path, low_memory=False)
    issues: list[str] = []

    missing_required = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_required:
        issues.append(f"Missing required columns: {missing_required}")

    if "datetime" in df.columns:
        parsed = pd.to_datetime(df["datetime"], errors="coerce")
        fail_rate = float(parsed.isna().mean() * 100)
        if fail_rate > 0:
            issues.append(f"Datetime parse failure rate: {fail_rate:.1f}%")

    if {"image_path", "label_path"}.issubset(df.columns):
        image_match_rate = float((df["image_path"].fillna("") != "").mean() * 100)
        if image_match_rate < 95:
            issues.append(f"Image-label match rate is low: {image_match_rate:.1f}%")

    for col in MODEL_COLUMNS:
        if col in df.columns:
            missing_rate = float(df[col].isna().mean() * 100)
            if missing_rate > 80:
                issues.append(f"High missing rate for {col}: {missing_rate:.1f}%")

    return df, issues


def write_validation_report(input_path: str | Path, output_path: str | Path) -> Path:
    df, issues = validate_features(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 데이터 품질 검증 보고서",
        "",
        f"- 입력 파일: `{input_path}`",
        f"- 전체 행 수: `{len(df)}`",
        f"- 전체 컬럼 수: `{len(df.columns)}`",
        "",
        "## 컬럼",
        "",
        ", ".join(f"`{col}`" for col in df.columns),
        "",
        "## 돈방별 건수",
        "",
    ]

    if "chamber_number" in df.columns:
        lines.append(dataframe_to_markdown(df.groupby("chamber_number").size().to_frame("count")))
    else:
        lines.append("`chamber_number` 컬럼이 없습니다.")

    lines += [
        "",
        "## 결측률",
        "",
        dataframe_to_markdown((df.isna().mean() * 100).round(2).to_frame("missing_percent")),
        "",
        "## 이슈",
        "",
    ]

    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- 주요 품질 이슈가 발견되지 않았습니다.")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate normalized pig anomaly feature CSV.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="artifacts/data_validation_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = write_validation_report(args.input, args.output)
    print(f"report: {report}")


if __name__ == "__main__":
    main()
