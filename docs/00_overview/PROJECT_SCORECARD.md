# 프로젝트 종합 스코어카드

작성일: 2026-08-30
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

지금까지의 성과가 `docs/04_evaluation_validation/` 아래 여러 문서에 흩어져 있어, 발표/심사용으로 한 장에서 볼 수 있도록 정리했다. 상세 근거는 각 링크된 문서를 참고한다.

시각 대시보드(이 문서의 내용을 한 페이지로): https://claude.ai/code/artifact/2bd24514-948a-408b-886a-f6eff4900466
관리자용 운영 대시보드 프로토타입(실제 파이프라인 산출값 + 확인/오탐 처리 인터랙션): https://claude.ai/code/artifact/28c93b1f-bbf1-40fe-ade8-8092d52c3bf0

## 1. 한 줄 요약

AI Hub 양돈 생체/행동 데이터로 돈방 단위 정상 패턴을 학습하고, 모델 기반 이상점수와 수의학/사양관리/환경 규칙을 결합해 조기 경보 및 현장 대응 큐를 만드는 프로젝트다. 목표는 ASF 확진이 아니라 이상 후보 조기 선별이다.

## 2. 메인 파이프라인 현재 성능 (AI Hub 71408/71763 기준)

| 항목 | 결과 |
| --- | --- |
| 최종 alert window | 26 / 131 |
| disease alert | 20 |
| management alert | 기본 데이터 0, synthetic 검증 2 |
| environment alert | 6 |
| candidate `co2_high=1100` 적용 시 | disease 20 유지, environment 6 → 0 |

상세: [PROJECT_OVERVIEW_BIGDATA_FLOW.md](PROJECT_OVERVIEW_BIGDATA_FLOW.md)

## 3. 외부 데이터 검증 7개 트랙

AI Hub 데이터는 전부 "정상으로 가정"한 데이터라 진짜 이상 사례가 없다. 아래 7개로 파이프라인(모델 + 규칙)을 실제 라벨과 대조 검증했다.

| # | 데이터셋 | 성격 | 핵심 결과 |
| --- | --- | --- | --- |
| 1 | HOTPIG | 열스트레스 (동물 다름) | TN 0.94% → HS 11.83% (12.6배) |
| 2 | ASF Dryad | 실제 ASF challenge | sensitivity 48.7% / specificity 99.5% / precision 95.0% |
| 3 | Behavior x Heat Tolerance | 열스트레스 보조 | 행동+근육온도 조합에서만 강하게 분리 |
| 4 | AI Hub 71471 | 발정행동 라벨 | 622와 feature mapping 17/17, 메인 학습 제외 |
| 5 | Wearable Stress Biosensor | 격리 스트레스 (심박/호흡 실측) | Pair 0% → Isolation 39.7% |
| 6 | PRRSV Play Study | 다른 질병(호흡기) challenge | 같은 온도 threshold가 ASF(99.5%)/PRRSV(32.9%)에서 다르게 작동 |
| 7 | **ClearFarm** | **비육돈 실제 농장** | 4개 규칙 전부 절대 threshold 비전이성 확인, 재캘리브레이션 시 precision 47.5% |

상세: [EXTERNAL_VALIDATION_SUMMARY.md](../04_evaluation_validation/EXTERNAL_VALIDATION_SUMMARY.md)

## 4. 비육돈(ClearFarm) 특화 결과 -- 프로젝트 목표 기준 첫 실제 성능 숫자

프로젝트의 1차 목표는 "비육돈 돈방 이상탐지"이지만, 지금까지 성능 숫자는 전부 실험실 challenge이거나 생산단계 미상 데이터였다. ClearFarm이 처음으로 실제 비육돈 + 실제 건강관찰 라벨을 제공했다.

| 규칙 | 설정값 | 원래 성능 | 재캘리브레이션 |
| --- | --- | --- | --- |
| `feed_drop` (일단위) | z-score ≤ -1.5 | 수학적으로 발동 불가 (이론적 상한 1.1547) | 시간 단위로 재집계 → sensitivity 37.3% / specificity 67.4% / precision 40.8% |
| `co2_high` | ≥1000ppm | 상시 발동 (specificity 0.2%) | 2984ppm(best-F1) → precision 32.6% |
| `nh3_high` | ≥10ppm | 상시 발동 (specificity 0.0%) | 29ppm(best-F1) → precision 24.5% |
| `barn_temp_high` | ≥40도 | 전혀 미발동 (관측 최댓값 35.6도) | 31.6도(p95) → **sensitivity 47.5% / specificity 97.1% / precision 47.5%** |
| `feed_drop AND co2_high` | 복합 | -- | precision 46.2% (단일 규칙 대비 상승) |
| LSTM baseline (모델 기반) | -- | -- | 방향은 맞으나 신호 약함 (표본 부족) |

### 4-1. ClearFarm 점수화 scorecard

개별 규칙을 OR/AND로만 보지 않고, `feed_drop`, `co2_high`, `nh3_high`, `barn_temp_high`를 severity weight + co-occurrence bonus 방식으로 점수화했다. 이는 메인 파이프라인의 `rule_score` 철학과 같은 구조다.

| 점수 기준 | 목적 | 성능 |
| --- | --- | --- |
| `rule_score >= 0.3` | 조기 선별 우선 | sensitivity **73.1%** / specificity 29.9% / precision 37.1% / F1 **49.2%** |
| `rule_score >= 0.6` | 중간 균형 | sensitivity 52.5% / specificity 50.2% / precision 37.4% / F1 43.7% |
| `rule_score >= 0.9` | 알림 수 절감 | sensitivity 26.1% / specificity 83.0% / precision 46.4% / F1 33.4% |
| `environment_score >= 0.9` vs heat signs | 고온/환경성 이상 고정밀 후보 | sensitivity 42.5% / specificity **98.5%** / precision **53.1%** / F1 47.2% |

### 4-2. 3단계 알림 정책

ClearFarm scorecard를 운영 행동으로 바꿔 `observe -> caution -> cctv_focus` 정책을 구현했다.

| 단계 | 조건 | ClearFarm 라벨 기준 결과 |
| --- | --- | --- |
| observe | `rule_score >= 0.3` | 212 pen-day, any signs 36.3% |
| caution | `rule_score >= 0.6` | 316 pen-day, any signs 31.3% |
| cctv_focus | `rule_score >= 0.9` 또는 `environment_score >= 0.9` | 211 pen-day, any signs **46.4%**, heat signs 9.5% |

주의: `normal` 단계도 any signs 33.8%라서 이 정책은 “정상 판정기”가 아니라 CCTV/현장 확인 우선순위를 정하는 triage 정책이다.

**결론: 규칙 방향성 자체는 유효하지만, 절대값 threshold 하나를 여러 농장/데이터셋에 공유하는 설계가 문제다.** ClearFarm 기준으로는 `rule_score >= 0.3`이 조기 선별용, `rule_score >= 0.9` 또는 `environment_score >= 0.9`가 고확신 알림용 후보다. 다음 단계는 농장별 상대 threshold 구조 -- [FARM_RELATIVE_THRESHOLD_DESIGN.md](../03_modeling_and_rules/FARM_RELATIVE_THRESHOLD_DESIGN.md)에 설계만 해두었고, `config/domain_rules.json`(메인 파이프라인이 실제 쓰는 파일)은 아직 수정하지 않았다.

상세: [CLEARFARM_RULE_VALIDATION_REPORT.md](../04_evaluation_validation/CLEARFARM_RULE_VALIDATION_REPORT.md), [clearfarm_rule_scorecard_report.md](../../artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_scorecard_report.md), [CLEARFARM_3LEVEL_ALERT_POLICY.md](../05_operations_feedback/CLEARFARM_3LEVEL_ALERT_POLICY.md)

## 5. 최초 기획 대비 완성도

| 최초 기획 항목 | 달성률 | 비고 |
| --- | --- | --- |
| 돈방별 정상 패턴 학습 | 80% | |
| Anomaly Score 생성 | 80% | |
| 질병 의심도 계산 | 68% | AI Hub 기준. ClearFarm scorecard로 규칙 점수 threshold 후보 확보 |
| 사료/음수 이상 반영 | 45% | ClearFarm 시간 단위 feed_drop 검증 및 scorecard 반영 완료, 음수 실데이터는 아직 부족 |
| 환경 보정 | 68% | ClearFarm 후보 config와 scorecard 구현 완료, 메인 운영 config 미반영 |
| 이상 돈방 선정 | 78% | ClearFarm 3단계 triage 정책 구현 완료 |
| CCTV 집중 분석 | 35% | 팀원 YOLO 결과 연동 전 |
| 이상 개체 특정 | 15% | 아직 통합 전 |
| 관리자 알림/대시보드 | 55% | 인터랙티브 프로토타입 완성(확인/오탐 처리), 실데이터 연동/배포 전 |
| 리뷰 기반 개선 | 60% | |

전체 1차 목표("비육돈 돈방 이상탐지 조기 선별") 68-72% 수준. 상세 및 최신 업데이트: [PROJECT_DIRECTION_DETAILED_PLAN.md](PROJECT_DIRECTION_DETAILED_PLAN.md)

## 6. 알려진 한계 (정직하게)

- ASF 확진 모델이 아니라 이상 후보 조기 선별 모델이다.
- 메인 파이프라인의 성능 숫자(섹션 2)는 AI Hub "정상 가정" 데이터 기준이라, 실제 확진/증상 라벨 기반 recall/precision이 아니다.
- 외부 검증 7개 중 실제 비육돈 + 실제 라벨 조합은 ClearFarm 하나뿐이고, 개체수/기간이 제한적이다.
- `config/domain_rules.json`의 절대 threshold는 ClearFarm 검증에서 데이터셋마다 다르게 실패한다는 게 확인됐지만, 아직 프로덕션에 재캘리브레이션이 반영되지 않았다.
- CCTV 기반 개체 특정, 관리자 대시보드는 아직 미완성이다.

## 7. 특허 후보 (CO-SHOW 채점: 특허출원 가능성 25점)

3건 선정, 선행기술(`1020210047517`, `KR101133719B1`) 대비 차별점 정리 완료. 확정된 특허성 판단이 아니라 변리사 상담 전 1차 스크리닝이다.

| 후보 | 핵심 | 실측 근거 |
| --- | --- | --- |
| 1. 농장별 상대 threshold 자동 캘리브레이션 | 고정 threshold 대신 농장 자체 분포로 재계산 | barn_temp_high 40도(0%)→31.6도(47.5%) |
| 2. Disease/Management/Environment 분리형 co-occurrence 스코어링 | 카테고리는 분리, 동시발생은 재통합 | feed_drop+co2_high precision 41%→46.2%, 3중 결합은 tp=0 |
| 3. 이종 시간축/개체군 트랙 표준화 결합 | 물리적으로 안 겹치는 두 데이터셋 점수를 하나의 돈방 경보로 | `final_ensemble.py` 구현 완료, 실가중결합은 검증 대기 |

상세(청구항 초안 포함): [PATENT_CANDIDATES.md](../06_ip_and_business/PATENT_CANDIDATES.md) &middot; 상담 요청 자료: [CONSULTATION_PACKAGE.md](../06_ip_and_business/CONSULTATION_PACKAGE.md)

## 8. 다음 단계 우선순위

1. ClearFarm 3단계 정책 산출물을 메인 action queue 형식으로 변환하는 어댑터 구현
2. 농장별 상대 threshold를 `domain_rules.json`/`domain_rules.py`에 실제로 반영 (설계는 완료, 구현 대기)
3. 팀원 YOLO 결과와 CCTV 집중 분석 연동
4. 관리자 알림/대시보드 UI
5. 실제 농장 이벤트 로그 확보 (지금은 synthetic 이벤트로만 검증)
