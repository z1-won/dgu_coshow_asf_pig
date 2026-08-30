# 현장 지식 기반 기준 적용 계획

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

> **업데이트 (2026-08-26, 돈방별 scaler 적용 후)**: 5절의 `bioenergy_clean_baseline_no_nh3` 수치가 바뀌었습니다. `p99 threshold: 1.442694` → `2.298732`. `excluded_rows`도 26개에서 0개로 바뀌었습니다(자세한 이유는 [CLEAN_BASELINE_MODEL_REPORT.md](../03_modeling_and_rules/CLEAN_BASELINE_MODEL_REPORT.md) 업데이트 노트 참고). raw anomaly 1개, confirmed anomaly 0개는 동일합니다. 이 문서의 rule layer 설계 방향 자체는 그대로 유효합니다.
>
> **업데이트 (2026-08-30, 비육돈 실제 농장 검증 이후)**: 4절의 예시 규칙들(`T_mean >= 40` 등)이 실제 비육돈 농장(ClearFarm)에서는 그대로 작동하지 않는다는 걸 확인했습니다 -- `co2_high`/`nh3_high`는 상시 발동(specificity 0%대), `barn_temp_high`(40도)는 전혀 발동 안 함(관측 최댓값 35.6도), `feed_drop`은 입력을 하루 단위로 집계하면 z-score가 수학적으로 threshold(-1.5)에 도달 못 함. 이유와 재캘리브레이션 결과는 [CLEARFARM_RULE_VALIDATION_REPORT.md](../04_evaluation_validation/CLEARFARM_RULE_VALIDATION_REPORT.md)에, "절대 threshold 하나를 여러 농장에 공유하는 대신 농장별 상대 threshold로 가야 한다"는 설계 제안은 [FARM_RELATIVE_THRESHOLD_DESIGN.md](FARM_RELATIVE_THRESHOLD_DESIGN.md)에 정리했습니다. `config/domain_rules.json`(메인 파이프라인이 실제 쓰는 파일)은 아직 수정하지 않았습니다.

## 1. 질문

예를 들어 온도가 40도 이상이면 이상하다는 지식을 모델에 추가해도 되는가?

답은 가능하다. 다만 모델 학습에 바로 섞는 것보다, 처음에는 규칙 기반 보조 판단으로 분리해서 붙이는 방식을 권장한다.

## 2. 권장 방식

권장 구조는 2단계다.

1. LSTM Autoencoder
   - 정상 패턴과 다른 흐름을 anomaly score로 계산한다.
   - 온도, 체온, 호흡, 환기, 열량 등 여러 피처의 시간 흐름을 종합해서 본다.

2. Domain rule layer
   - 사람이 이미 알고 있는 위험 기준을 별도로 검사한다.
   - 예: 돈사 온도 과고온, 체온 과고온, 급수량 급감, 환기량 급변 등

최종 알림은 두 결과를 함께 본다.

```text
alert = model_anomaly OR hard_rule_violation
```

또는 점수형으로 합칠 수 있다.

```text
final_score = 0.7 * model_score + 0.3 * rule_score
```

## 3. 왜 바로 학습에 섞지 않는가

규칙을 학습 데이터에 바로 섞으면 다음 문제가 생길 수 있다.

- 규칙이 틀렸을 때 모델 전체가 왜곡된다.
- 농장, 계절, 일령, 돈방 조건에 따라 정상 범위가 달라질 수 있다.
- 예외 상황을 모델이 무조건 이상으로 학습할 수 있다.
- 어떤 이유로 알림이 발생했는지 설명하기 어려워진다.

그래서 처음에는 규칙과 모델을 분리하고, 알림 단계에서 합치는 것이 더 안전하다.

## 4. 적용 가능한 규칙 예시

아래 값은 예시이며, 실제 운영 전에는 수의사/현장 전문가와 조정해야 한다.

| 구분 | 예시 규칙 | 의미 |
| --- | --- | --- |
| 돈사 온도 | `T_mean >= 40` | 환경 고온 위험 후보 |
| 직장 체온 | `rectal_temperature_mean >= 40` | 체온 이상 후보 |
| 호흡수 | 평소 baseline 대비 급증 | 스트레스/이상 후보 |
| 급수량 | 평소 baseline 대비 급감 | 급수 문제 후보 |
| 환기량 | 급격한 변화 또는 비정상 고정 | 설비/환경 이상 후보 |
| CO2 | 평소 baseline 대비 급증 | 환기 불량 후보 |

주의:

- `T_mean >= 40`은 돈사 환경 온도 기준으로는 매우 높은 값이다.
- `rectal_temperature_mean >= 40`은 돼지 체온 기준에서 별도 해석이 필요하다.
- 같은 40도라도 돈사 온도와 돼지 체온은 의미가 다르다.

## 5. 현재 모델에 반영한 변경

이번 변경에서는 `NH3_mean`을 모델 피처에서 제외했다.

이유:

- 사용자가 암모니아 제외를 요청했다.
- 현재 설명 그래프에서 암모니아가 주요 요인으로 올라왔지만, 현장 센서 신뢰도나 해석 기준이 확정되지 않으면 모델 판단을 흔들 수 있다.
- 제외 후에도 baseline 모델은 정상 기준으로 작동한다.

변경 후 모델:

- 산출물 경로: `artifacts/bioenergy_clean_baseline_no_nh3`
- 입력 피처 수: 23
- 제외 피처: `NH3_mean`
- p99 threshold: `1.442694`
- p99 raw anomaly: 1개
- p99 confirmed anomaly: 0개

## 6. 다음 구현 권장

다음 단계에서는 `domain_rules.json`을 만들고, 탐지 결과에 rule 결과를 함께 붙인다.

예상 파일:

- `config/domain_rules.json`
- `src/pigproject/domain_rules.py`
- `artifacts/.../bioenergy_rule_flags.csv`
- `artifacts/.../bioenergy_combined_alert_report.md`

리포트에는 아래처럼 표시한다.

| window | model anomaly | rule anomaly | 주요 사유 |
| --- | --- | --- | --- |
| 1 | False | True | `T_mean >= 40` |
| 2 | True | False | reconstruction error threshold 초과 |
| 3 | True | True | 모델 이상 + 체온 기준 초과 |

이렇게 하면 AI 모델의 패턴 감지와 사람이 아는 위험 기준을 함께 설명할 수 있다.
