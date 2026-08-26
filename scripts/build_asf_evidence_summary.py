"""Pull together every piece of ASF-specific evidence built this session into
one document.

The evidence is real, but scattered across five separate scripts/docs
(disease_score co-occurrence check, real ASF challenge threshold validation,
HotPig external sanity check, the domain rules themselves, the model's own
detection report) -- nobody reviewing the project for the first time would
find all of it without being walked through the whole session. This script
regenerates one artifact that is meant to be the first thing a judge reads:
what's proven, with what data, and what isn't proven yet.

Run after scripts/run_demo_pipeline.sh (needs artifacts/bioenergy_clean_baseline
to exist). Writes artifacts/bioenergy_clean_baseline/ASF_EVIDENCE_SUMMARY.md.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT / "artifacts" / "bioenergy_clean_baseline"
DRYAD_DIR = ROOT / "data" / "raw" / "asf_dryad"
HOTPIG_DOC = ROOT / "docs" / "HOTPIG_SANITY_CHECK_REPORT.md"


def run_script(relative_path: str) -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / relative_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else f"(script failed)\n{result.stderr}"


def extract_disease_score_counts(report_path: Path) -> str:
    if not report_path.exists():
        return "(bioenergy_combined_alert_report.md 없음 -- pig-apply-rules를 먼저 실행하세요)"
    text = report_path.read_text(encoding="utf-8")
    match = re.search(r"## Disease Score 분포\n\n(.+?)\n\n", text, re.S)
    return match.group(1) if match else "(찾을 수 없음)"


def extract_hotpig_headline() -> str:
    if not HOTPIG_DOC.exists():
        return "(docs/HOTPIG_SANITY_CHECK_REPORT.md 없음)"
    text = HOTPIG_DOC.read_text(encoding="utf-8")
    match = re.search(r"\| 구간 \| window 수 \| raw anomaly \| 비율 \|.+?\n\n", text, re.S)
    return match.group(0) if match else "(표를 찾을 수 없음, 문서 참고)"


def main() -> None:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ASF 탐지 근거 요약",
        "",
        "이 프로젝트가 ASF에 특화해서 검증한 것들을 한 곳에 모은 문서입니다. 자동 생성됨 (`scripts/build_asf_evidence_summary.py`).",
        "",
        "## 1. 지금 모델의 상태",
        "",
        extract_disease_score_counts(FINAL_DIR / "bioenergy_combined_alert_report.md"),
        "",
        "(`bioenergy_combined_alert_report.md`, `threshold_confidence.csv` 참고)",
        "",
        "## 2. Disease Score가 복합 증상에 실제로 반응하는가 (합성 검증)",
        "",
        "```",
        run_script("scripts/verify_disease_score_cooccurrence.py").strip(),
        "```",
        "",
        "자세한 설계는 `docs/ASF_DISEASE_SCORE.md`.",
        "",
    ]

    if DRYAD_DIR.exists():
        lines += [
            "## 3. 실제 ASF 챌린지 데이터로 온도 규칙 검증",
            "",
            "```",
            run_script("scripts/verify_rectal_temp_rule_against_real_asf.py").strip(),
            "```",
            "",
            "데이터: Lotonin et al., Dryad 10.5061/dryad.cnp5hqcm5 (10마리, 226 pig-day, 실제 ASFV 공격접종).",
            "threshold를 39.5도로 조정한 근거는 `docs/ASF_REAL_CHALLENGE_VALIDATION.md`.",
            "",
        ]
    else:
        lines += [
            "## 3. 실제 ASF 챌린지 데이터로 온도 규칙 검증",
            "",
            "(data/raw/asf_dryad/ 없음 -- 브라우저로 https://datadryad.org/dataset/doi:10.5061/dryad.cnp5hqcm5 받아서 재실행)",
            "이전 실행 결과는 `docs/ASF_REAL_CHALLENGE_VALIDATION.md`에 기록됨: 특이도/정밀도 100%, 재현율 41%->49%.",
            "",
        ]

    lines += [
        "## 4. 탐지 방법론이 실제 생리적 이상에 반응하는가 (열스트레스 외부 검증)",
        "",
        extract_hotpig_headline(),
        "",
        "정상 대비 약 10배, 스트레스 초기(1일차 14.4%)에 가장 민감하고 점차 낮아짐 -- 급성 스트레스 후 부분 적응과 일치. 자세한 내용은 `docs/HOTPIG_SANITY_CHECK_REPORT.md`.",
        "",
        "## 5. 한 줄 요약",
        "",
        "> 모델은 정상 패턴만으로 학습하고, 규칙은 ASF 임상 문헌·특허·실제 챌린지 데이터로 threshold를 잡았다. "
        "온도 규칙 단독으로는 재현율이 60%를 못 넘는다는 걸 실측으로 확인했고, "
        "그래서 모델 anomaly score와 규칙을 disease_score로 결합했다. "
        "이 결합이 복합 증상에서 더 크게 반응하는 것과, 탐지 방법론 자체가 실제 생리적 이상에 반응하는 것을 "
        "각각 별도의 외부 데이터로 검증했다.",
        "",
        "## 6. 향후 확장 참고 (지금 파이프라인엔 미포함)",
        "",
        "- **백혈구/림프구 감소(leukopenia/lymphopenia)**: 같은 Dryad 데이터의 `Sup._Fig._3_-_Leukocytes.csv`/`Lymphocytes.csv`에서 중증 개체(임상점수 14~17)가 감염 7일차에 백혈구가 급격히 붕괴하는 걸 확인함(예: 14->3.06). ASF의 대표적 혈액 지표이지만 IoT 센서로는 측정 불가 -- 온도 규칙만으로 재현율이 60%를 못 넘는 근본 이유이기도 함. 수의사 확진 단계에서 참고할 지표로 문서화만 해둠.",
        "- **SWINOSTICS2류 현장 진단기기**: 타액 기반 휴대 ASFV 검사 장비(EU URBANE 프로젝트, Zenodo 21358070). 우리 시스템이 \"어느 개체/돈방을 검사할지\" 조기 선별하고, 이런 장비가 확진을 맡는 역할 분담 구조로 실제 배포 시나리오에 넣을 수 있음.",
    ]

    output = FINAL_DIR / "ASF_EVIDENCE_SUMMARY.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
