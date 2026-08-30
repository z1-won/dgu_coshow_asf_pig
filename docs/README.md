# PigProject 문서 읽는 순서

이 폴더는 빅데이터분석기사의 분석 절차에 맞춰 다시 정리했다.
처음 보는 사람은 모든 문서를 한 번에 읽지 말고 아래 순서대로 보면 된다.

## 1. 먼저 읽을 문서

1. [프로젝트 전체 흐름](00_overview/PROJECT_OVERVIEW_BIGDATA_FLOW.md)
2. [프로젝트 방향 및 세부 계획](00_overview/PROJECT_DIRECTION_DETAILED_PLAN.md)
3. [초심자용 모델 설명](00_overview/MODEL_EXPLANATION_FOR_NEWCOMERS.md)
4. [병렬 데이터 트랙](01_data_understanding/PARALLEL_DATA_TRACKS.md)
5. [해외 Pig Dataset 후보](01_data_understanding/OVERSEAS_PIG_DATASET_CANDIDATES.md)
6. [해외 데이터 다운로드 계획](01_data_understanding/OVERSEAS_DATA_DOWNLOAD_PLAN.md)
7. [PRRSV Play Study 작업 계획](01_data_understanding/PRRSV_PLAY_STUDY_WORK_PLAN.md)
8. [ASFV Challenge Dryad 작업 계획](01_data_understanding/ASFV_CHALLENGE_DRYAD_WORK_PLAN.md)
9. [ClearFarm/RFID/Feeding 데이터 활용 계획](01_data_understanding/CLEARFARM_RFID_FEEDING_DATA_USAGE_PLAN.md)
10. [외부 검증 요약](04_evaluation_validation/EXTERNAL_VALIDATION_SUMMARY.md)
10-1. [Wearable Stress Biosensor 검증](04_evaluation_validation/STRESS_BIOSENSOR_VALIDATION.md)
11. [규칙 기반 판단 가이드](03_modeling_and_rules/DOMAIN_RULE_GUIDANCE.md)
12. [위험 카테고리 경보](05_operations_feedback/RISK_CATEGORY_ALERTS.md)
13. [다음 작업 계획](00_overview/NEXT_STEPS.md)

## 2. 폴더 구조

| 폴더 | 역할 | 먼저 볼 문서 |
| --- | --- | --- |
| `00_overview` | 목적, 전체 흐름, 현재 상태 | `PROJECT_OVERVIEW_BIGDATA_FLOW.md` |
| `01_data_understanding` | 데이터 선택, AI Hub 데이터셋, 추가 데이터 계획 | `PARALLEL_DATA_TRACKS.md` |
| `02_data_preparation` | 전처리, split, scaler, 시계열 한계 | `SPLIT_IMPROVEMENT_REPORT.md` |
| `03_modeling_and_rules` | LSTM baseline, 온도 보정, domain rule, disease score | `DOMAIN_RULE_GUIDANCE.md` |
| `04_evaluation_validation` | threshold, 외부 검증, sanity check, ensemble 판단 | `EXTERNAL_VALIDATION_SUMMARY.md` |
| `05_operations_feedback` | 현장 이벤트, action queue, review feedback | `RISK_CATEGORY_ALERTS.md` |

## 3. 한 줄 요약

이 프로젝트는 AI Hub 양돈 생체/행동 데이터를 이용해 돈방 단위 정상 패턴을 학습하고, 모델 기반 이상점수와 수의학/사양관리/환경 규칙을 결합해 조기 경보 및 현장 대응 큐를 만드는 프로젝트다.
