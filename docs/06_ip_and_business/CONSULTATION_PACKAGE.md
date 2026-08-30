# 산학협력단/변리사 상담 요청 자료

작성일: 2026-08-30
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 한 줄 요청

CO-SHOW 경진대회(예선 2026-09-04) 출품작의 특허 후보 3건에 대해, (1) 발표 전 가출원 필요 여부, (2) 신규성/진보성 1차 의견을 상담받고자 합니다.

## 프로젝트 한 줄 소개

돈방(비육돈 사육 구역) 단위로 정상 패턴을 학습하고, 모델 기반 이상점수와 질병/사양관리/환경 규칙을 결합해 이상 징후를 조기 경보하는 시스템입니다. ASF(아프리카돼지열병) 확진이 아니라 이상 돈방 조기 선별이 목표입니다.

## 상담 요청 사항 (우선순위 순)

1. **시급**: 8/30 발표 자료가 이미 준비돼 있고 9/4 예선 발표를 앞두고 있습니다. 발표/공개 전에 가출원(임시출원)이 필요한지, 필요하다면 오늘~내일 중 가능한 절차가 있는지 확인 부탁드립니다.
2. 아래 특허 후보 3건 중 신규성/진보성이 가장 높아 보이는 것부터 우선순위를 매겨주시면 좋겠습니다.
3. 학생 경진대회 출품작 특허 출원 시 학교/학생 간 권리 관계(직무발명 여부 등)도 함께 안내받고 싶습니다.

## 특허 후보 3건 요약

| # | 후보 | 핵심 | 확인한 선행기술 |
| --- | --- | --- | --- |
| 1 | 농장별 상대 임계값 자동 캘리브레이션 | 고정 절대 threshold 대신 각 농장의 최근 데이터 분포로 threshold를 자동 산출 | `1020210047517`, `KR101133719B1`, `KR101382627B1`, `US8297231B2` 계열은 전부 고정/사전설정 threshold. 범용 적응형 threshold 특허(`WO2021176460A1`)는 존재하나 축산 도메인 아님 |
| 2 | Disease/Management/Environment 분리형 co-occurrence 스코어링 | 이상 규칙을 3개 카테고리로 나누되, 같은 카테고리 내 동시발생 시 점수 가산 | `KR101133719B1`은 분리만 하고 미통합, `US8297231B2` 계열은 통합만 하고 미분리 |
| 3 | 이종 시간축/개체군 트랙 표준화 결합 | 물리적으로 안 겹치는 두 데이터셋의 이상점수를 표준화 후 병기/결합 | 직접 겹치는 선행기술을 웹검색으로 찾지 못함 (다만 정식 조사 아님) |

상세 배경/구성/청구항 초안: [PATENT_CANDIDATES.md](PATENT_CANDIDATES.md)

## 첨부 자료 (프로젝트 경로 기준)

- 특허 후보 상세 노트 + 청구항 초안: `docs/06_ip_and_business/PATENT_CANDIDATES.md`
- 후보 1 실측 근거: `docs/04_evaluation_validation/CLEARFARM_RULE_VALIDATION_REPORT.md`, `docs/03_modeling_and_rules/FARM_RELATIVE_THRESHOLD_DESIGN.md`
- 후보 1 실제 구현 코드: `src/pigproject/rule_candidate_config.py`, `src/pigproject/clearfarm_rule_validation.py`, `config/domain_rules_clearfarm.json`
- 후보 2 실제 구현 코드: `src/pigproject/domain_rules.py` (특히 `evaluate_rules` 함수), `config/domain_rules.json`
- 후보 3 실제 구현 코드: `src/pigproject/final_ensemble.py`
- 이미 참고한 선행 특허: `docs/03_modeling_and_rules/TEMPERATURE_ONLY_BASELINE_REPORT.md` 2절 (`1020210047517` 요약)
- 프로젝트 전체 요약: `docs/00_overview/PROJECT_SCORECARD.md`

## 참고 -- 이 자료의 한계

이 문서와 `PATENT_CANDIDATES.md`는 AI(Claude Code)가 웹 공개 검색만으로 작성한 1차 스크리닝입니다. KIPRIS 전체 조사, 출원인 자격, 청구항 문언은 전문가 검토가 필요합니다.
