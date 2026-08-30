# 농장별 상대 threshold 설계안

작성일: 2026-08-30
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 왜 필요한가

`docs/04_evaluation_validation/CLEARFARM_RULE_VALIDATION_REPORT.md`에서 `config/domain_rules.json`의 절대값 threshold 4개(`feed_drop`, `co2_high`, `nh3_high`, `barn_temp_high`)가 ClearFarm(비육돈 실제 농장)에 그대로 옮겨지지 않는다는 걸 확인했다. 원인은 규칙 방향성이 아니라, **하나의 절대값을 여러 농장/데이터셋에 공유하는 설계** 자체에 있다:

- `co2_high`(≥1000ppm), `nh3_high`(≥10ppm): ClearFarm 기저치가 훨씬 높아 상시 발동(specificity 0.0~0.2%)
- `barn_temp_high`(≥40도): ClearFarm 관측 범위(최대 35.6도)를 벗어나 전혀 발동 안 함
- `feed_drop`(z-score ≤ -1.5): 일단위로 뭉갠 입력에서는 표본 3개 z-score의 이론적 상한(1.1547)에 걸려 수학적으로 도달 불가 -- 이건 이번 세션에서 시간 단위로 재집계해서 이미 해결했다(`clearfarm_feed_drop_subdaily_report.md`, sensitivity 37.3%/specificity 67.4%/precision 40.8%)

**barn_temp_high를 ClearFarm 자체 분포(p95=31.6도)로 재캘리브레이션하자 precision이 47.5%까지 회복됐다.** 이건 "규칙 자체는 유효하고, 절대값 하나를 고정한 설계가 문제"라는 가설을 뒷받침하는 직접 증거다. 이번 문서는 이 가설을 실제 코드 설계로 옮기기 위한 제안이다.

## 이번 세션에서 확인한 재캘리브레이션 결과 (참고용)

| 규칙 | 원래 threshold | 원래 성능 | 재캘리브레이션 threshold | 재캘리브레이션 성능 |
| --- | --- | --- | --- | --- |
| `barn_temp_high` | 40도 | sensitivity 0% | p95=31.6도 | sensitivity 47.5% / specificity 97.1% / precision 47.5% |
| `co2_high` | 1000ppm | specificity 0.2% | best-F1=2984ppm(≈p50) | sensitivity 63.2% / specificity 54.8% / precision 32.6% |
| `nh3_high` | 10ppm | specificity 0.0% | best-F1=29ppm | sensitivity 42.3% / specificity 47.8% / precision 24.5% |

CO2/NH3는 재캘리브레이션해도 precision이 barn_temp_high만큼 깨끗하게 오르지 않는다 -- 이건 CO2/NH3 자체가 respiratory_signs 단독 예측력이 약하다는 뜻일 수 있고(관찰 기록의 잡음일 수도 있음), 재캘리브레이션이 만능은 아니라는 점도 같이 기록해둔다.

## 설계 옵션

### 옵션 A. 규칙 config에 "relative" threshold 타입 추가

`config/domain_rules.json`의 각 rule에 `threshold_type: "absolute" | "relative_percentile"`을 추가하고, `relative_percentile`인 경우 `threshold`를 percentile(0~100)로 해석해서 **평가 시점에 그 데이터셋/농장의 최근 N일 분포에서 percentile 값을 계산**해 실제 threshold로 쓴다.

```json
{
  "id": "co2_high",
  "category": "environment",
  "feature": "CO2_mean",
  "agg": "max",
  "op": ">=",
  "threshold_type": "relative_percentile",
  "threshold": 90,
  "baseline_window_days": 30,
  "baseline_group_by": ["dataset_key", "chamber_number"],
  "severity": "low"
}
```

장점: 규칙 정의가 하나로 유지되고, 데이터셋마다 자동으로 재캘리브레이션된다.
단점: `evaluate_rules`가 지금은 순수 함수(윈도우 테이블 + 규칙 리스트만 있으면 됨)인데, percentile 계산을 하려면 "최근 N일 baseline"을 어디서 가져올지(같은 윈도우 테이블 안에서 계산할지, 별도 캘리브레이션 스텝을 먼저 돌릴지) 아키텍처를 정해야 한다.

### 옵션 B. 캘리브레이션을 별도 전처리 스텝으로 분리

각 데이터셋을 붙일 때 "캘리브레이션 스텝"을 한 번 실행해서, 그 데이터셋 전용 `domain_rules_<dataset>.json`(절대값으로 구체화된 규칙 파일)을 생성한다. 이미 있는 `rule_candidate_config.py`/`rule_config_compare.py` 패턴(원본 대비 후보 config 비교)을 그대로 재사용할 수 있다.

```bash
pig-calibrate-rules --dataset clearfarm --percentile 95 --output config/domain_rules_clearfarm.json
```

장점: `evaluate_rules` 자체는 전혀 안 바뀐다 -- 지금처럼 절대값 config를 읽는 구조 그대로 두고, config 생성 단계만 데이터셋별로 나눈다. 위험이 훨씬 작다.
단점: 데이터셋이 늘어날 때마다 별도 config 파일을 만들어야 하고, "언제 재캘리브레이션했는지" 버전 관리가 필요하다.

### 권장

**옵션 B를 먼저 채택한다.** 이유:

1. `evaluate_rules`/`domain_rules.py`는 지금 메인 ASF 파이프라인(71408/71763/622)이 실제로 쓰고 있는 코드다. 오늘 같은 마감일에 이 핵심 로직을 직접 바꾸면 메인 파이프라인 전체를 다시 검증해야 하는 위험이 있다.
2. `rule_candidate_config.py`(candidate config 생성) + `rule_config_compare.py`(비교 리포트)가 이미 있어서, 옵션 B는 기존 도구를 거의 그대로 재사용할 수 있다 -- 새 코드가 적다.
3. 옵션 A(규칙 엔진 자체에 relative 타입 내장)는 여러 농장 데이터가 실제로 쌓이기 시작하면(지금은 ClearFarm 하나) 그때 정식으로 설계하는 게 낫다 -- 지금 하나의 사례만으로 엔진을 일반화하면 과설계 위험이 있다.

## 실행 결과 (2026-08-30)

2단계를 실제로 실행했다. 기존 `pig-build-rule-candidate-config`(옵션 B 전제 도구)가 이미 다중 threshold override를 지원해서 새 코드 없이 바로 썼다.

```bash
pig-build-rule-candidate-config \
  --base-config config/domain_rules.json \
  --overrides "co2_high=2984,nh3_high=29,barn_temp_high=31.6" \
  --output-config config/domain_rules_clearfarm.json
pig-compare-rule-configs \
  --artifact-dir artifacts/bioenergy_clean_baseline \
  --baseline-rules config/domain_rules.json \
  --candidate-rules config/domain_rules_clearfarm.json
```

**중요한 발견**: 이 ClearFarm 캘리브레이션 config를 메인 AI Hub 파이프라인 데이터(`bioenergy_clean_baseline`)에 그대로 적용해보면, disease alert는 20개로 유지되지만 **environment alert가 6개에서 0개로 전부 사라진다** (`artifacts/clearfarm_rule_validation/rule_config_compare_report.md`). ClearFarm 기준으로 훨씬 높게 잡은 CO2/NH3 threshold가 AI Hub의 (상대적으로 낮은) CO2/NH3 값에는 아예 걸리지 않기 때문이다.

이건 이 설계안의 핵심 주장을 다시 한번 실증한다: **ClearFarm 전용으로 만든 config는 ClearFarm에서만 써야 하고, 다른 데이터셋(AI Hub)에 그대로 재사용하면 안 된다.** `config/domain_rules_clearfarm.json`은 그 용도로만 유지하고, 메인 파이프라인이 실제로 읽는 `config/domain_rules.json`은 이번에도 수정하지 않았다.

## 다음 단계 (아직 실행 안 함)

1. ~~ClearFarm 기준 `config/domain_rules_clearfarm.json` 생성~~ 완료
2. `clearfarm_rule_validation.py`가 하드코딩된 threshold 상수 대신 `config/domain_rules_clearfarm.json`을 직접 읽도록 리팩터링 (지금은 상수와 config 파일 값이 우연히 같을 뿐, 코드로 연결돼 있지 않음)
3. 농장이 2개 이상 쌓이면 옵션 A(규칙 엔진 내장) 재검토

**주의**: `config/domain_rules.json`(메인 파이프라인이 실제로 쓰는 파일)은 여전히 수정하지 않았다. 실제 config 교체(예: 메인 파이프라인이 데이터셋별로 다른 config를 자동 선택하게 만드는 것)는 별도 승인 후 진행한다.
