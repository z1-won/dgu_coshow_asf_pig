# Risk Category 분리 경보 설계

목적: 모든 규칙을 `disease_score` 하나로 밀어 넣지 않고, 실제 운영에서 다른 대응이 필요한 신호를 분리한다.

## Category

| category | 의미 | 대표 규칙 |
| --- | --- | --- |
| `disease` | 질병/발열 의심 | `rectal_temp_high`, `neck_temp_high` |
| `management` | 사양관리 이상 | `feed_drop`, `water_drop`, `water_spike` |
| `environment` | 환경/설비 이상 | `barn_temp_high`, `co2_high`, `nh3_high`, `ventilation_low_with_co2_high` |

## 계산 방식

- 각 rule은 `config/domain_rules.json`에서 `category`를 가진다.
- `disease_rule_score`, `management_rule_score`, `environment_rule_score`를 따로 계산한다.
- `disease_score`는 기존 호환성을 위해 유지하지만, 이제 질병 관련 rule과 model component 중심으로 계산한다.
- `management_score`, `environment_score`는 별도 컬럼으로 저장한다.
- `alert_category`는 해당 window에서 켜진 category를 `disease`, `management`, `environment`로 표시한다.

## 현재 재계산 결과

`artifacts/bioenergy_clean_baseline/bioenergy_rule_flags.csv` 기준:

| 항목 | 값 |
| --- | ---: |
| 전체 window | 61 |
| disease alert | 20 |
| management alert | 0 |
| environment alert | 6 |
| final alert | 26 |

`data/processed/final_chamber_anomaly_scores.csv` 기준:

| 항목 | 값 |
| --- | ---: |
| 전체 window | 131 |
| final alert | 26 |
| operational alert | 26 |

## 중요한 해석

규칙 강화 후 final alert는 `20 -> 26`으로 늘었다. 하지만 새로 늘어난 6개는 질병 경보가 아니라 `co2_high + nh3_high` 조합으로 인한 `environment` 경보이다. 따라서 "질병 recall이 올라갔다"고 말하면 안 되고, "환경/설비성 이상 후보를 별도 경보로 볼 수 있게 됐다"고 해석해야 한다.

`feed_drop`, `water_drop`은 injection 검증에서 rule은 정상적으로 켜진다. 다만 현재 실제 validation window에는 해당 패턴이 없어 management alert는 0이다.

## 다음 개선 포인트

실제 운영에서는 `final_alert`를 하나로만 보지 말고 다음처럼 화면/리포트를 나누는 것이 맞다.

- disease queue: 수의학적 확인 우선
- management queue: 급이/급수/사양관리 확인 우선
- environment queue: 환기/공기질/설비 확인 우선
