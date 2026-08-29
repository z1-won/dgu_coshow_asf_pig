# 프로젝트 전체 흐름: 빅데이터분석기사 기준

작성일: 2026-08-30  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 1. 비즈니스 이해

이 프로젝트의 목적은 ASF를 확진하는 것이 아니다. 목적은 돈방 단위로 정상 패턴에서 벗어나는 이상 후보를 조기 선별하고, 현장 작업자가 확인할 수 있도록 경보를 분류하는 것이다.

최종 사용자는 다음 질문에 답을 얻어야 한다.

- 어떤 돈방이 평소와 다른가?
- 그 이상이 질병 의심인가, 사양관리 문제인가, 환경/설비 문제인가?
- 먼저 무엇을 확인해야 하는가?
- 현장 확인 결과를 다시 모델/규칙 개선에 쓸 수 있는가?

따라서 최종 산출물은 단순한 모델 점수가 아니라 `final alert -> action queue -> incident queue -> review log -> rule tuning`으로 이어지는 운영 흐름이다.

## 2. 데이터 이해

현재 데이터는 세 축으로 나뉜다.

| 데이터 | 역할 | 현재 판단 |
| --- | --- | --- |
| AI Hub 71408/71763 생체 에너지 | 메인 모델/규칙 트랙 | 최종 경보의 중심 |
| AI Hub 622 행동/키포인트 | 행동량 보조 트랙 | 최종 테이블에는 병렬 통합, 가중 결합은 보류 |
| AI Hub 71471 발정행동 keypoint | 행동 feature 보조 검증 | 메인 ensemble에는 미포함 |

71408/71763은 체온, 환경, 급이/급수, 활동/호흡 관련 feature가 있어 이상탐지와 domain rule에 직접 쓸 수 있다. 622는 행동량 feature를 만들 수 있지만 71408/71763과 같은 농장/같은 기간의 돈방이 아니어서 아직 물리적 돈방 단위 가중 결합은 하지 않는다. 71471은 keypoint와 발정 라벨은 있지만 ASF/체온/환경 라벨이 없고 channel confounding이 있어 보조 검증용으로만 둔다.

먼저 볼 문서:

- [병렬 데이터 트랙](../01_data_understanding/PARALLEL_DATA_TRACKS.md)
- [71471 통합 계획](../01_data_understanding/AIHUB_71471_INTEGRATION_PLAN.md)
- [외부 검증 요약](../04_evaluation_validation/EXTERNAL_VALIDATION_SUMMARY.md)

## 3. 데이터 준비

데이터 준비 단계에서는 AI Hub JSON/라벨을 모델이 읽을 수 있는 공통 시계열 CSV로 바꿨다.

주요 처리:

- 원천 JSON/라벨 정규화
- 돈방별 timestamp 정렬
- 10분 또는 window 단위 집계
- 결측/비정상 센서값 점검
- 돈방별 scaler 적용
- LSTM Autoencoder 입력 window 생성
- train/validation split 개선

중요한 수정은 돈방별 scaler다. 전체 데이터를 하나의 scaler로 정규화하면 돈방마다 원래 값 수준이 다른 것이 이상처럼 보일 수 있다. 그래서 현재는 돈방 단위 정상 패턴을 더 공정하게 보기 위해 돈방별 scaler를 사용한다.

먼저 볼 문서:

- [Split 개선 리포트](../02_data_preparation/SPLIT_IMPROVEMENT_REPORT.md)
- [행동량 전처리 감사](../02_data_preparation/ACTIVITY_PREPROCESSING_AUDIT.md)
- [돈방 시계열 한계](../02_data_preparation/CHAMBER_TIMESERIES_LIMITATION.md)

## 4. 모델링

모델링은 두 층으로 구성된다.

첫 번째는 LSTM Autoencoder다. 정상 패턴을 학습하고, 재구성 오차가 큰 window를 이상 후보로 본다. 즉 질병을 직접 분류하는 모델이 아니라 정상과 얼마나 다른지를 보는 모델이다.

두 번째는 domain rule layer다. 모델이 놓칠 수 있는 수의학/사양관리/환경 신호를 사람이 해석 가능한 규칙으로 계산한다.

현재 risk category는 다음처럼 나뉜다.

| category | 의미 | 예시 rule |
| --- | --- | --- |
| disease | 수의학적 확인 우선 | `rectal_temp_high`, `neck_temp_high` |
| management | 급이/급수/사양관리 확인 | `feed_drop`, `water_drop`, `water_spike` |
| environment | 환기/가스/온습도 확인 | `co2_high`, `nh3_high`, `ventilation_low` |

최종 disease score는 모델 점수와 disease rule score를 합친다. management와 environment는 disease로 과장하지 않고 별도 score와 queue로 분리한다.

먼저 볼 문서:

- [Clean baseline 모델](../03_modeling_and_rules/CLEAN_BASELINE_MODEL_REPORT.md)
- [Domain rule 가이드](../03_modeling_and_rules/DOMAIN_RULE_GUIDANCE.md)
- [ASF disease score](../03_modeling_and_rules/ASF_DISEASE_SCORE.md)
- [온도 보정](../03_modeling_and_rules/ASF_TEMPERATURE_CORRECTION.md)

## 5. 평가

평가는 accuracy 하나로 보지 않는다. 현재 프로젝트는 이상탐지 성격이 강하고 실제 확진 라벨이 충분하지 않기 때문에 여러 검증 축을 함께 본다.

평가 축:

- threshold별 경보 수 변화
- p95/p97/p99 reconstruction error 비교
- ASF challenge 외부 데이터로 체온 threshold sanity check
- HOTPIG heat stress 데이터로 행동/온도 feature sanity check
- 71471 keypoint 데이터로 행동 feature 보조 검증
- category별 lead-time recall
- rule 추가 전후 비교
- candidate threshold 실험

현재 대표 결과:

| 항목 | 결과 |
| --- | --- |
| 최종 alert window | 26 / 131 |
| disease alert | 20 |
| management alert | 기본 데이터 0, synthetic 검증 2 |
| environment alert | 6 |
| candidate `co2_high=1100` | disease 20 유지, environment 6 -> 0 |

먼저 볼 문서:

- [Threshold 비교](../04_evaluation_validation/THRESHOLD_COMPARISON_REPORT.md)
- [ASF 실제 challenge 검증](../04_evaluation_validation/ASF_REAL_CHALLENGE_VALIDATION.md)
- [HOTPIG sanity check](../04_evaluation_validation/HOTPIG_SANITY_CHECK_REPORT.md)
- [Ensemble 데이터 결정](../04_evaluation_validation/ENSEMBLE_DATA_DECISIONS.md)

## 6. 배포/운영 관점

현재는 서비스 배포 전 단계지만, 운영 흐름을 미리 만들었다.

운영 흐름:

```text
final_chamber_anomaly_scores.csv
-> category action queues
-> incident_queue.csv
-> incident_review_log_template.csv
-> rule_tuning_recommendations.csv
-> candidate rule config experiment
```

이 흐름을 통해 경보를 단순 점수로 끝내지 않고, 현장 확인과 rule 개선으로 되돌릴 수 있다.

현재 생성 가능한 운영 산출물:

- `artifacts/action_queues/disease_queue.csv`
- `artifacts/action_queues/management_queue.csv`
- `artifacts/action_queues/environment_queue.csv`
- `artifacts/action_queues/incident_queue.csv`
- `data/templates/incident_review_log_template.csv`
- `artifacts/rule_tuning_recommendations_report.md`
- `config/domain_rules_candidate_co2_1100.json`

먼저 볼 문서:

- [농장 이벤트 스키마](../05_operations_feedback/FARM_EVENT_DATA_SCHEMA.md)
- [위험 카테고리 경보](../05_operations_feedback/RISK_CATEGORY_ALERTS.md)
- [다음 작업 계획](NEXT_STEPS.md)

## 7. 지금 가능한 것과 아직 어려운 것

가능한 것:

- 돈방 단위 이상 후보 탐지
- 체온/환경/사양관리 rule 기반 설명
- disease/management/environment 경보 분리
- action queue와 incident queue 생성
- 현장 리뷰 로그 템플릿 생성
- 리뷰 결과 기반 rule 조정 후보 산출
- 후보 rule config를 별도로 만들어 비교

아직 어려운 것:

- ASF 확진 판정
- 같은 물리적 돈방에서 생체 에너지와 행동량 트랙을 가중 평균 결합
- 실제 농장 장기 운영 데이터 기반 precision/recall 확정
- management rule의 실제 recall/precision 확정
- 환경 rule threshold의 운영 확정

## 8. 추천 읽기 순서

1. 이 문서
2. [초심자용 모델 설명](MODEL_EXPLANATION_FOR_NEWCOMERS.md)
3. [병렬 데이터 트랙](../01_data_understanding/PARALLEL_DATA_TRACKS.md)
4. [외부 검증 요약](../04_evaluation_validation/EXTERNAL_VALIDATION_SUMMARY.md)
5. [Domain rule 가이드](../03_modeling_and_rules/DOMAIN_RULE_GUIDANCE.md)
6. [위험 카테고리 경보](../05_operations_feedback/RISK_CATEGORY_ALERTS.md)
7. [다음 작업 계획](NEXT_STEPS.md)

## 9. 한 문장 요약

AI Hub 양돈 생체/행동 데이터를 이용해 돈방 단위 정상 패턴을 학습하고, 모델 기반 이상점수와 수의학/사양관리/환경 규칙을 결합해 조기 경보 및 현장 대응 큐를 만드는 프로젝트다.
