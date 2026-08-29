# Disease Score: 증상 동시발생 가중 결합

작성일: 2026-08-26
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 1. 왜 필요했나

`config/domain_rules.json`의 규칙들과 LSTM 모델의 anomaly 판정은 지금까지 단순 OR로만 합쳐져 있었다 (`final_alert = model_anomaly OR rule_anomaly`). 이러면 "고열만 있음"과 "고열 + 사료섭취 급감 + 활동량 감소가 동시에"가 똑같은 취급을 받는다.

베어메모의 GPT 가설(H1-3)도 이 지점을 짚는다: "한 우리 안에서 고위험 발열 개체 비율이 증가하고 **동시에** 활동량이 감소하면, 단순 환경성 고온보다 질병성 이상징후일 가능성이 증가한다." 즉 여러 증상이 한 window에서 같이 나타나는 게 그 자체로 추가 정보다. 원래 설계였던 "① 돈방 이상도(Anomaly Score) → ② 질병 의심도(Disease Score) → ③ CCTV 개체 특정"의 ②번을 실제로 구현한 것이 이 문서다.

## 2. 계산 방식

`src/pigproject/domain_rules.py`의 `evaluate_rules()` / `combine_with_model()`에서 계산한다.

```text
rule_score = Σ(severity_weight for 걸린 규칙) + co_occurrence_bonus
co_occurrence_bonus = 0.3 * max(0, 걸린 규칙 수 - 1)

model_component = 0.5 * min(reconstruction_error / threshold, 2.0)

disease_score = model_component + rule_score
```

- `severity_weight`: high=1.0, medium=0.6, low=0.3 (`config/domain_rules.json`의 규칙별 `severity` 필드 기준)
- `co_occurrence_bonus`: 규칙이 2개 이상 동시에 걸리면 추가 규칙 1개당 +0.3. 예를 들어 `rectal_temp_high`(고열, high=1.0) 하나만 걸리면 rule_score=1.0이지만, 여기에 `feed_drop`(medium=0.6)까지 같이 걸리면 rule_score = 1.0 + 0.6 + 0.3(보너스) = 1.9로, 단순 합(1.6)보다 더 크게 나온다.
- `model_component`: 모델 재구성 오차가 threshold의 몇 배인지를 0.5 가중치로 반영하고, 2배에서 상한을 둬서 한 window의 극단값이 점수를 독점하지 않게 했다.
- `rule_observation`: 낮은 심각도 환경 신호(`co2_high` 같은 low severity)도 기록한다.
- `rule_anomaly`: category별 기준을 넘은 경우 최종 경보 후보로 올린다. 현재 기준은 disease 0.8, management 0.6, environment 0.8이다. low severity 단독 신호는 관찰로만 남기고, 복합 신호나 중간 이상 신호만 category alert로 승격한다.

## 3. Tier 구분

| tier | 기준 |
| --- | --- |
| high | disease_score >= 1.5 |
| medium | disease_score >= 0.8 |
| normal | 그 외 |

이 컷오프는 임의로 정한 시작값이다. 실제 확인된 이상 사례가 쌓이면(또는 5순위 계획인 합성 증상 주입 테스트로) 재조정이 필요하다 -- 지금은 "단일 증상은 medium, 복합 증상은 high로 넘어가도록" 설계된 값이다.

## 4. 현재 데이터에서 확인된 것

`bioenergy_clean_baseline` 기준 최신 rule layer는 사양관리/환경 규칙을 포함한다. 현재 실제 validation window에서는 `feed_drop`, `water_drop`, `ventilation_low`가 직접 걸리지는 않았고, 추가로 걸린 것은 `co2_high`, `nh3_high` 환경 신호다. 낮은 심각도 단독 환경 신호는 `rule_observation`으로만 남기고, `co2_high + nh3_high`처럼 동시발생으로 `environment_rule_score >= 0.8`이 된 경우만 환경 경보로 승격한다.

최신 결과:

- 전체 bioenergy validation window: 61
- rule observation: 41
- rule anomaly: 26
- high tier: 10 (`rectal_temp_high + co2_high`)
- medium tier: 16 (`rectal_temp_high` 단독 또는 `co2_high + nh3_high`)
- final ensemble alert window: 20 -> 26

이 결과는 규칙 추가만으로 경보 범위를 넓힐 수 있음을 보여준다. 다만 현재 보유 데이터에서는 급이/급수 급감 자체가 validation window에 나타나지 않아 `feed_drop`, `water_drop` recall 개선은 실제 또는 주입형 테스트 데이터에서 따로 확인해야 한다.

### 검증 완료 (`scripts/verify_disease_score_cooccurrence.py`)

실제 `evaluate_rules()`/`disease_tier_for()` 코드 경로에 합성 window 3개를 통과시켜 확인했다. model_component는 세 시나리오 모두 0.45로 고정해서(재구성 오차 영향 배제), 규칙 동시발생 효과만 분리해서 봤다.

| 시나리오 | 걸린 규칙 | rule_severity_sum | co_occurrence_bonus | disease_score | tier |
| --- | --- | ---: | ---: | ---: | --- |
| control (정상) | 없음 | 0.00 | 0.00 | 0.45 | normal |
| fever_only (고열 단독) | rectal_temp_high | 1.00 | 0.00 | 1.45 | medium |
| combined (고열+섭취급감+음수급증 동시) | rectal_temp_high, feed_drop, water_spike | 1.90 | 0.60 | 2.95 | **high** |

설계대로 단일 증상은 medium, 복합 증상은 high로 확실히 갈린다. `python scripts/verify_disease_score_cooccurrence.py`로 재현 가능.

## 5. 산출물

각 `artifacts/bioenergy_*` 디렉터리의:
- `bioenergy_rule_flags.csv`: window별 `disease_score`, `disease_tier`, `rule_score`, `rule_triggered_count`, `model_component` 포함
- `bioenergy_combined_alert_report.md`: tier별 개수 + `disease_tier == high` window 목록
