# 데이터셋 추가 실행 설계

작성일: 2026-08-30

## 1. 설계 기준

현재 프로젝트의 가장 큰 병목은 모델 구조가 아니라 데이터 커버리지다. 그래서 데이터셋 추가는 “많이 모으기”가 아니라, 현재 성능이 약한 축을 보강하는 순서로 진행한다.

현재 약한 축은 다음이다.

1. 실제 농장 기반 `feed_drop`, `environment_failure`, `respiratory` 검증
2. 질병 challenge 기반 체온/임상/행동/사료 변화 검증
3. 활동량 정상 baseline과 `activity_drop` 기준 확정
4. heat stress와 질병성 이상 구분
5. YOLO/CV 자세 detect 결과와 LSTM/Rule 결과 결합

## 2. 현재 데이터 상태

| 데이터 | 상태 | 프로젝트 위치 | 현재 처리 상태 |
| --- | --- | --- | --- |
| ClearFarm Growing-Finishing Pig Sensor Dataset | 다운로드 완료 | `data/raw/external/clearfarm_growing_finishing/` | `clearfarm_pen_day.csv` 1차 생성 완료 |
| RFID-LoRaWAN Pig Movement Dataset | 다운로드 완료 | `data/raw/external/rfid_lorawan_movement_17266727/` | `rfid_pig_hour.csv`, `rfid_pig_day.csv` 생성 완료 |
| Pig Feeding Behaviour Dataset 5126661 | 다운로드 완료 | `data/raw/external/pig_feeding_behavior_5126661/` | raw 복사/인벤토리 완료, reference summary 필요 |
| PRRSV Disease Resilience Dataset | 다운로드 완료 | `data/raw/external/prrsv_play_study/` | sheet inventory 완료, timeline 생성 필요 |
| ASFV Challenge Dataset | 다운로드 완료 | `data/raw/external/asfv_challenge_dryad/` | timeline/threshold sweep 완료 |
| Pig Stress & Gait IoT Dataset | 일부/완료 확인됨 | `data/raw/external/wearable_stress_biosensor/` | raw 확인 완료, profiling 필요 |
| Pig Multimodal Wearable Dataset | 다운로드 중 | `data/raw/external/pig_multimodal_behavior/` 예정 | 완료 후 검증 |
| Behavior x Heat Tolerance | 다운로드 필요/확인 필요 | `data/raw/external/behavior_heat_tolerance/` 예정 | 기존 sanity 결과는 있으나 raw 통합 필요 |
| Behaviour Analysis During Heat Stress in Pigs | 다운로드 필요/확인 필요 | `data/raw/external/mendeley_heat_stress_behavior/` 예정 | 완료 후 검증 |

## 3. 추가 데이터셋별 역할

### 3.1 ClearFarm

역할: 현재 프로젝트에 가장 직접적으로 연결되는 실제 비육돈 농장 데이터.

보강하는 축:

- feeding/management
- environment
- health observation
- removal/slaughter event
- 상반기 일부 데이터: 2021년 1-3월, 2022년 5월

이미 생성된 산출물:

- `data/processed/external/clearfarm/clearfarm_pen_day.csv`
- `artifacts/external/clearfarm/clearfarm_pen_day_report.md`

다음 보완점:

- Exp1 health observation이 현재 pen-day health 집계에서 일부 누락될 수 있으므로 pen/ivog 매핑 보정 필요
- feed filling/ghost visit 제거 기준 재검증
- `feed_drop`, `environment_failure`, `respiratory`, `removal_event` 후보 라벨 생성

### 3.2 RFID-LoRaWAN Movement

역할: 활동량 정상 baseline 생성.

보강하는 축:

- activity baseline
- activity_drop threshold
- 개체별/시간대별 이동량 정상 변동성

이미 생성된 산출물:

- `data/processed/external/rfid_lorawan/rfid_pig_hour.csv`
- `data/processed/external/rfid_lorawan/rfid_pig_day.csv`

다음 보완점:

- `activity_drop_zscore` 기준 후보 정리
- 24시간 미만 관측일 제외/표시
- AI Hub 622 행동량 feature와 범위 비교

### 3.3 Pig Feeding Behaviour 5126661

역할: 정상 급이 행동 reference table.

보강하는 축:

- 개체당 일일 사료섭취량 정상 범위
- 급이 방문 횟수
- 방문당 섭취량
- 급이 속도

한계:

- 날짜가 없어 lead-time 평가에는 부적합
- 시계열이 아니라 요약형 baseline으로 사용

다음 산출물:

- `artifacts/external/pig_feeding_behavior_5126661/feeding_reference_summary.csv`
- `artifacts/external/pig_feeding_behavior_5126661/feeding_reference_report.md`

### 3.4 PRRSV Disease Resilience

역할: 실제 감염 challenge에서 체온/임상/행동/사료 변화 검증.

보강하는 축:

- disease 일반 신호
- respiratory/cough/appetite
- feeding behaviour
- treatment
- viral load

한계:

- ASF가 아니라 PRRSV
- pig-level challenge라 chamber-level 메인 모델에 직접 섞지 않음

다음 산출물:

- `data/processed/external/prrsv_play_study/prrsv_daily_timeline.csv`
- `artifacts/external/prrsv_play_study/prrsv_external_validation_report.md`

### 3.5 ASFV Challenge

역할: ASF 체온/clinical score 검증.

이미 나온 핵심 수치:

- 39.5도 threshold 기준 recall 48.7%
- specificity 99.5%
- precision 95.0%
- F1 64.4%

해석:

- 체온 rule은 정밀도는 높지만 recall은 낮다.
- ASF 확진 모델이 아니라 ASF 의심 조기 선별 모델이라는 포지션을 강화한다.

다음 보완점:

- 결과를 `performance_scorecard.md`와 최종 보고서에 반영
- PRRSV와 비교해 “ASF 특이 근거”와 “질병 일반 근거”를 분리

### 3.6 Pig Stress & Gait IoT

역할: HR/BR/accelerometer 기반 stress physiology 보조 검증.

현재 확인된 raw:

- `Supplementary File S1.csv`: 318,714 rows, 44 columns
- 주요 컬럼: `Animal`, `Activity`, `HR`, `BR`, `SkinTemp`, `Posture`, `PeakAccel`, accelerometer axes

보강하는 축:

- respiration/heart rate 기반 stress signal
- wearable 기반 activity/stress feature
- 현재 bioenergy의 `breath_rate` 계열 해석 보조

한계:

- 개체 수가 작을 가능성이 높음
- 돈방/환경/사료와 직접 연결은 약함

다음 산출물:

- `artifacts/external/wearable_stress_biosensor/wearable_stress_profile_report.md`
- `data/processed/external/wearable_stress_biosensor/wearable_stress_timeseries.csv`

### 3.7 Pig Multimodal Wearable

역할: lying/eating/walking/drinking 행동 분류 보조 데이터.

보강하는 축:

- 행동 라벨 기반 feature 검증
- 팀원 YOLO 자세 detect의 label taxonomy 비교
- 행동 기반 anomaly feature 설계

한계:

- wearable/audio 기반이라 CCTV와 센서 형태가 다름
- 메인 모델에 직접 섞기보다 행동 feature 검증에 사용

### 3.8 Heat Stress 행동 데이터 2종

대상:

- Behavior x Heat Tolerance
- Behaviour Analysis During Heat Stress in Pigs

역할:

- heat stress와 질병성 이상을 구분하는 confounder 검증
- 고온 환경에서 drinking/feeding/lying/standing/movement 변화 확인
- 여름철 false positive 조정

보강하는 축:

- heat_stress rule
- environment rule
- behavior-only signal의 한계 설명

## 4. 실행 우선순위

### 1순위: ClearFarm rule validation 완성

이유:

- 실제 비육돈 농장 데이터다.
- feeding, climate, health observation이 같은 pen/date에 붙는다.
- 현재 가장 약한 management/environment 성능을 직접 보강한다.

작업:

1. Exp1 health observation pen 매핑 보정
2. `clearfarm_pen_day.csv` 재생성
3. feed_drop 후보 라벨 생성
4. environment_failure 후보 라벨 생성
5. respiratory 후보 라벨 생성
6. removal/slaughter event를 운영 이벤트로 정리
7. rule validation report 작성

완료 기준:

- `artifacts/external/clearfarm/clearfarm_rule_validation_report.md`
- `data/processed/external/clearfarm/clearfarm_rule_events.csv`

### 2순위: PRRSV daily timeline 생성

이유:

- 실제 감염 challenge에서 체온/행동/사료/처치/viral load가 함께 있다.
- 현재 disease rule과 management rule 사이의 연결을 보강한다.

작업:

1. header row/profile 확정
2. rectal temperature 표준화
3. clinical signs 표준화
4. feeding behaviour/feed intake 결합
5. treatment/viral load 결합
6. disease lead-time proxy 산출

완료 기준:

- `prrsv_daily_timeline.csv`
- `prrsv_external_validation_report.md`

### 3순위: RFID activity baseline 확정

이유:

- 이미 processed 파일이 있다.
- 활동량 감소 rule을 빠르게 보강할 수 있다.

작업:

1. low_data_day 제외 기준 확정
2. 개체별 daily distance 정상 범위 계산
3. `activity_drop_zscore` 후보 threshold 산출
4. AI Hub 622 행동량 feature와 비교

완료 기준:

- `rfid_activity_baseline_report.md`
- `activity_drop_rule_candidate.csv`

### 4순위: 5126661 feeding reference 생성

이유:

- 작고 빠르게 처리 가능하다.
- ClearFarm feed feature의 기준값을 해석하는 데 도움된다.

작업:

1. 변수별 분포 요약
2. sex/station/body weight별 차이 확인
3. ClearFarm per-pig feed intake와 단위 비교
4. feed_drop rule 설명용 기준표 생성

완료 기준:

- `feeding_reference_report.md`

### 5순위: Wearable stress biosensor profiling

이유:

- HR/BR/accelerometer가 있어 stress physiology 보조 근거가 된다.
- 현재 bioenergy의 호흡/활동 관련 feature 해석에 도움된다.

작업:

1. 결측/비정상값 처리
2. activity별 HR/BR/SkinTemp/PeakAccel 분포 확인
3. stress condition별 생리 변화 확인
4. 현재 disease/activity rule과 매핑

완료 기준:

- `wearable_stress_profile_report.md`

### 6순위: Pig Multimodal Wearable 처리

이유:

- 다운로드 완료 후 행동 라벨 검증에 유용하다.
- 다만 1.1GB라 먼저 파일 검증과 샘플 profiling부터 한다.

완료 기준:

- `multimodal_behavior_inventory_report.md`
- `multimodal_behavior_label_summary.csv`

### 7순위: Heat Stress 행동 데이터 처리

이유:

- heat stress와 disease anomaly를 구분하는 데 필요하다.
- 여름철 false positive 보정에 도움된다.

완료 기준:

- `heat_stress_behavior_validation_report.md`

## 5. 통합 데이터 모델

모든 외부 데이터는 바로 하나의 학습셋으로 섞지 않는다. 대신 공통 스키마로 요약한다.

### 5.1 공통 관측 단위

| 단위 | 사용 데이터 | 목적 |
| --- | --- | --- |
| `pen_day` | ClearFarm | 돈방/pen 단위 management/environment/health event |
| `pig_day` | PRRSV, RFID, 5126661 | 개체 단위 체온/행동/급이/활동 baseline |
| `pig_time` | wearable stress, multimodal | 고해상도 생리/행동 feature |
| `challenge_day` | ASFV, PRRSV | 질병 challenge threshold/lead-time 검증 |
| `frame_or_clip` | PigLife/YOLO 예정 | 개별 돼지 localization 및 자세 근거 |

### 5.2 프로젝트 score로 연결

| 프로젝트 score/category | 추가 데이터 근거 |
| --- | --- |
| `disease_score` | ASFV clinical/temperature, PRRSV clinical/temperature/viral load |
| `management_score` | ClearFarm feeding, 5126661 feeding reference, PRRSV feed intake |
| `environment_score` | ClearFarm climate, Heat stress datasets |
| `activity_score` | RFID movement, wearable accelerometer, multimodal behavior |
| `cv_evidence` | Pig Multimodal label taxonomy, PigLife/YOLO 예정 |

## 6. 성공 기준

데이터 추가가 성공했다는 기준은 “파일을 많이 받은 것”이 아니라 아래 산출물이 생기는 것이다.

| 목표 | 성공 기준 |
| --- | --- |
| management 성능 보강 | 실제 ClearFarm 기반 feed_drop 후보 이벤트 생성 |
| environment 성능 보강 | CO2/NH3/온습도 기반 environment_failure 후보 이벤트 생성 |
| disease 근거 보강 | ASFV/PRRSV threshold 및 lead-time 수치 추가 |
| activity 근거 보강 | RFID 기반 activity_drop threshold 후보 생성 |
| YOLO 결합 준비 | 행동 label taxonomy와 dashboard input schema 정리 |
| 상반기 우선 전략 | 1-5월 데이터 availability와 별도 평가 결과 생성 |

## 7. 당장 실행할 작업

다음 실행은 ClearFarm rule validation이다.

구체 순서:

1. ClearFarm Exp1 health observation 매핑 오류 보정
2. `clearfarm_pen_day.csv` 재생성
3. feed/environment/respiratory 후보 이벤트 생성
4. 상반기 1-5월 이벤트 빈도 분리
5. 기존 `domain_rules.json`과 비교해 rule 개선 후보 작성

이 순서가 가장 좋은 이유는 ClearFarm이 현재 받은 데이터 중 실제 비육돈 농장 운영 데이터에 가장 가깝고, 지금 프로젝트에서 가장 약한 management/environment recall을 직접 보강하기 때문이다.
