# ClearFarm 규칙 검증 종합 -- 비육돈 기준 첫 실제 성능 숫자

작성일: 2026-08-30
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`
데이터 출처: ClearFarm Growing-Finishing Pig Sensor Dataset -- 독일 상업농장, 비육돈 4개 round, `data/raw/external/clearfarm_growing_finishing/`

> **업데이트 (2026-08-30, 후속 작업)**: 이 문서 작성 이후 4가지를 추가로 진행했다.
>
> 1. **feed_drop 해상도 수정**: 원본 급이 로그(방문 단위 타임스탬프)를 시간 단위로 재집계해서 z-score cap 문제를 해결. -1.5 threshold가 실제로 발동(282/820일)하고 sensitivity 37.3%/specificity 67.4%/precision 40.8% 확보 -- `clearfarm_feed_drop_subdaily_report.md`.
> 2. **농장별 상대 threshold 설계안** 작성 -- `../03_modeling_and_rules/FARM_RELATIVE_THRESHOLD_DESIGN.md`. `config/domain_rules.json`은 아직 수정하지 않았다(메인 파이프라인 영향 때문에 별도 승인 필요).
> 3. **복합 규칙(co-occurrence) 검증**: `feed_drop AND co2_high` 조합이 단일 규칙(precision ~41%)보다 precision이 오름(46.2%, n_fires=132) -- `domain_rules.py`의 co-occurrence bonus 설계가 실제 라벨에서도 방향이 맞다는 걸 확인. 단, 3개 규칙을 전부 AND로 묶으면 tp=0이 되는 것도 확인(과도한 co-occurrence의 위험) -- `clearfarm_composite_rules_report.md`.
> 4. **ClearFarm 전용 LSTM Autoencoder baseline** 구축(`src/pigproject/clearfarm_baseline.py`, `clearfarm_baseline_evaluate.py`) -- 규칙이 아니라 모델 기반 탐지로 비육돈 성능을 처음 측정. 결과는 방향은 맞지만 약함(symptomatic mean error 0.790 > normal 0.591, 하지만 confirmed anomaly rate 차이는 0.0% vs 0.9%로 미미, threshold CI 상대폭 137%로 불안정) -- 정상 관측이 663일뿐이고 펜당 관찰 간격이 3~4일이라 규칙 기반 검증만큼 확실한 숫자는 아직 안 나온다. `clearfarm_baseline_detection_report.md`.

모듈: `src/pigproject/clearfarm_rule_validation.py`

## 왜 필요했나

지금까지 프로젝트의 성능 숫자(ASF Dryad, PRRSV, HOTPIG, Wearable Biosensor)는 전부 실험실 challenge 데이터이거나 생산단계가 명시되지 않은 데이터였다. **프로젝트의 1차 목표 자체가 "비육돈 돈방 이상탐지"인데, 정작 비육돈 기준 실제 탐지 성능 숫자가 하나도 없었다.** ClearFarm은 실제 건강관찰 라벨(cough, diarrhea, panting 등)이 있는 유일한 비육돈 데이터라 여기서 처음으로 그 숫자를 만들었다.

`config/domain_rules.json`의 11개 규칙 중 ClearFarm에 해당 센서가 있는 4개(`feed_drop`, `co2_high`, `nh3_high`, `barn_temp_high`)만 검증했다. 나머지(`rectal_temp_high`, `neck_temp_high`, `water_drop`, `water_spike`, `ventilation_low`)는 ClearFarm에 개체 체온/급수/환기량 센서가 없어 검증 자체가 불가능하다.

## 4개 규칙 결과 요약

| 규칙 | 설정된 threshold | 문제 | 재캘리브레이션 시 최선 성능 |
| --- | --- | --- | --- |
| `feed_drop` | z-score ≤ -1.5 | **일단위 데이터에서 수학적으로 발동 불가** (표본 3개 z-score 이론적 최댓값 1.1547 < 1.5) | pct 기반 대안도 단독으로는 약함(precision ~39~46%) |
| `co2_high` | ≥1000ppm | **상시 발동** (specificity 0.2%) -- ClearFarm 기저치가 훨씬 높음 | p90(4159ppm)까지 올려도 precision 46% |
| `nh3_high` | ≥10ppm | **상시 발동** (specificity 0.0%) | p90(43ppm)까지 올려도 precision 21% |
| `barn_temp_high` | ≥40도 | **한 번도 발동 안 함** (관측 최댓값 35.6도) | p95(31.6도)로 낮추면 sensitivity 47.5% / specificity 97.1% / precision 47.5% |

## 핵심 결론: 절대값 threshold는 데이터셋마다 양방향으로 실패한다

4개 규칙이 서로 다른 방식으로 실패했다는 게 우연이 아니다.

- `co2_high`/`nh3_high`: threshold가 이 농장 기준으로는 **너무 낮아서** 상시 발동
- `barn_temp_high`: threshold가 **너무 높아서** 전혀 발동 안 함
- `feed_drop`: threshold 크기 문제가 아니라 **z-score를 계산하는 입력 데이터의 샘플링 밀도**(하루 1행) 자체가 그 threshold에 도달할 수 없는 구조

**세 종류의 실패 모두 "하나의 절대값을 여러 농장/데이터셋에 공유한다"는 같은 설계에서 나온다.** ClearFarm 자체 분포로 재캘리브레이션하면(barn_temp_high 사례처럼) precision 47.5%까지 회복되는 걸 보면, 규칙의 방향성 자체는 유효하고 문제는 절대 threshold 하나를 고정한 설계에 있다.

## 한계

- 건강관찰이 25%일에만 있어 나머지 75%는 ground truth가 없다(관찰 안 한 날 = "정상"이 아니라 "모름").
- ClearFarm은 특정 국가/사육방식(deep straw bedding)의 농장이라, 여기서 재캘리브레이션한 threshold가 다른 농장에 또 그대로 옮겨질 거라 기대해서는 안 된다 -- 오히려 "농장마다 다시 잡아야 한다"는 이번 결론을 재확인할 뿐이다.
- "Pig removals/sickbay" 이벤트 라벨은 원본 계획이 가정했던 것과 달리 실제 데이터에 없어 사용하지 못했다.

## 발표에 쓸 수 있는 한 줄

> "실제 비육돈 농장 데이터(ClearFarm)로 처음 규칙을 검증한 결과, 4개 규칙 모두 설정된 절대값 threshold가 그대로는 작동하지 않았다(2개는 상시발동, 1개는 전혀 미발동, 1개는 구조적으로 불가능). 하지만 barn_temp_high를 이 농장 분포로 재캘리브레이션하자 precision 47.5%까지 회복됐다 -- 규칙의 방향성은 유효하며, 다음 단계는 농장별 절대 threshold가 아니라 농장별 상대 baseline(z-score/percentile) 구조로의 전환이다."
