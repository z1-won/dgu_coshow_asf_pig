# ClearFarm, RFID-LoRaWAN, 5126661 Feeding 데이터 활용 계획

작성일: 2026-08-30

> **업데이트 (2026-08-30)**: RFID-LoRaWAN 5.1단계(pig-hour/pig-day feature 생성)를 `src/pigproject/rfid_lorawan_movement_features.py`(`pig-build-rfid-movement-features`)로 완료했습니다. 결과와 데이터 이슈는 `artifacts/rfid_lorawan_movement/rfid_lorawan_movement_baseline_report.md`를 참고하세요.
>
> 처리 중 두 가지를 발견했습니다. (1) 원본 문서는 각 행이 이미 시간당 집계값이라고 설명하지만, 실제 파일은 같은 `(pig, day, hour)` 키가 최대 약 180번까지 서로 다른 distance 값으로 반복되는 원시 하위-시간 단위 기록입니다 -- 합산해서 시간당 총 이동거리를 재구성했습니다. (2) `activity_drop_pct_1d` 기준 최대 낙폭 상위 5건이 전부 20일차(마지막 날, `low_data_day=True`)에 몰려 있었습니다 -- 실제 활동량 감소가 아니라 출하로 관측이 중간에 끊긴 것이라, 완전성 플래그(`low_data_day`, `hours_observed`) 없이는 이 데이터가 거짓 activity_drop 신호로 잘못 쓰일 뻔했습니다.
>
> **업데이트 (2026-08-30, 6.1단계)**: 5126661 feeding reference table도 `src/pigproject/pig_feeding_behavior_reference.py`(`pig-build-feeding-reference`)로 완료했습니다. `DFIkg_day`(일일 급이량 kg/마리/일) 중앙값 2.31kg이 ClearFarm의 `daily_feed_intake_per_pig_kg` 중앙값 2.77kg과 같은 자릿수/범위로 나와 두 데이터셋이 서로 교차검증됩니다 -- 단위가 정확히 일치하는 이 한 컬럼만 비교했고, 급이 속도/방문 횟수 등 나머지는 두 데이터셋의 집계 단위가 달라 비교하지 않았습니다. 결과는 `artifacts/pig_feeding_behavior_5126661/feeding_reference_report.md`를 참고하세요.

## 1. 현재 확인된 데이터

이번에 확인한 로컬 데이터는 세 종류다.

| 데이터 | 원본 위치 | 프로젝트 위치 | 현재 판단 |
| --- | --- | --- | --- |
| ClearFarm Growing-Finishing Pig Sensor Dataset | `/Users/bangjiwon/Downloads/Raw sensor and manual data from an observational study on four rounds of growing-finishing pigs/` | `data/raw/external/clearfarm_growing_finishing/` | 현재 프로젝트에 가장 직접적으로 유용 |
| RFID-LoRaWAN Pig Movement Dataset | `/Users/bangjiwon/Downloads/17266727/` | `data/raw/external/rfid_lorawan_movement_17266727/` | 활동량 정상 baseline 및 activity_drop 보강용 |
| Pig Feeding Behaviour Dataset 5126661 | `/Users/bangjiwon/Downloads/5126661/` | `data/raw/external/pig_feeding_behavior_5126661/` | feed intake 정상 기준/feature 정의 보조용 |

주의: 사용자가 첨부한 `Raw sensor and manual data...`는 표의 2번 RFID가 아니라 표의 1번 ClearFarm 데이터로 확인된다. 다만 프로젝트에 매우 유용하므로 함께 정리했다.

## 2. 데이터별 규모와 특징

### 2.1 ClearFarm Growing-Finishing Pig Sensor Dataset

실제 독일 농장의 비육돈 4개 사육 round 관측 데이터다.

확인 규모:

| 항목 | 규모 |
| --- | ---: |
| feeding visit records | 1,119,042 rows |
| climate sensor records | 1,082,970 rows |
| on-farm health observation rows | 10,970 rows |
| pig registration | round별 110 pigs |
| 실험 round | 4개 |
| 관측 기간 | 2020-12 ~ 2022-12 |

포함 변수:

- 전자급이기 방문 기록: `pig`, `station`, `intake`, `start`, `end`, `duration`, `rate`
- 환경 센서: ammonia, CO2, humidity, temperature, 15분 단위
- 건강 관찰: cough, sneeze, diarrhea, lameness, panting, shivering, body condition, pen hygiene 등
- pig registration: pig ID, pen, station, gender, body weight
- pig removals: sickbay 이동, 출하/도태 등

프로젝트 적합도:

- 돈방/pen 단위 관측이라 현재 프로젝트의 1차 목표와 잘 맞음
- feeding + climate + health observation이 같은 round/pen 안에 있어 `feed_drop`, `environment_failure`, `respiratory`, `treatment/removal` 계열 평가에 유리
- Exp3가 2022-05-13 ~ 2022-08-24라 상반기 우선 전략 중 5월 데이터를 포함
- ASF는 아니지만 실제 농장 observational 데이터라 synthetic event보다 훨씬 설득력 있음

### 2.2 RFID-LoRaWAN Pig Movement Dataset

16마리, 20일간 RFID-LoRaWAN 기반 이동거리 데이터다.

확인 규모:

| 항목 | 규모 |
| --- | ---: |
| movement records | 1,048,573 rows |
| pigs | 16 |
| day range | 1-20 |
| hour range | 00:00-23:00 |
| columns | `pid_id`, `Day_s`, `distance`, `Hour` |

프로젝트 적합도:

- 활동량 정상 baseline 생성에 좋음
- 현재 `activity_drop` 또는 움직임 감소 rule의 외부 보조 데이터로 사용 가능
- 실제 날짜가 아니라 day index라 1-5월 계절 분석에는 직접 사용 불가
- 질병/건강 event 라벨은 없어 anomaly detector sanity check와 정상 변동성 기준에 적합

### 2.3 Pig Feeding Behaviour Dataset 5126661

개체별 급이 행동 요약 데이터다.

확인 규모:

| 항목 | 규모 |
| --- | ---: |
| rows | 587 |
| columns | 15 |
| 주요 변수 | `DFIkg_day`, `NDVvisits_day`, `FOmin_day`, `FIVg_visit`, `DUVmin_visit`, `FRg_min_day`, `BWs`, `age1`, `sex`, `station` |

프로젝트 적합도:

- 시계열 데이터가 아니라 개체별 요약 baseline에 가깝다.
- `정상 일일 사료섭취량`, `방문 횟수`, `방문당 섭취량`, `급이 속도`의 범위 산정에 유용하다.
- 직접 lead-time 평가에는 약하지만, ClearFarm feed feature 설계의 기준표로 사용 가능하다.

## 3. 프로젝트에 넣는 우선순위

| 우선순위 | 데이터 | 이유 | 먼저 만들 산출물 |
| --- | --- | --- | --- |
| 1 | ClearFarm | 실제 비육돈 + feeding + climate + health observation이 결합 가능 | pen-day 통합 테이블 |
| 2 | RFID-LoRaWAN | activity/movement 정상 baseline 보강 | pig-hour/day movement baseline |
| 3 | 5126661 Feeding | feed feature 정의와 정상 급이 범위 보조 | feeding feature reference table |

## 4. ClearFarm 세부 활용 계획

ClearFarm은 바로 프로젝트의 약점을 메울 수 있다. 특히 기존 프로젝트에서 약했던 항목은 management와 environment 쪽이다.

### 4.1 1단계: 표준화 및 인벤토리 확정

작업:

1. round별 feeding CSV 통합
2. Exp3의 `pig.short`를 표준 `pig_id`로 변환
3. registration 파일과 merge하여 `pen_id`, `station`, `compartment`, `experiment` 정리
4. climate long format을 15분/1시간/1일 단위로 pivot
5. on-farm observation health sheet를 long/pen-day 형식으로 정리

산출물:

- `data/processed/external/clearfarm/clearfarm_feeding_visits.csv`
- `data/processed/external/clearfarm/clearfarm_climate_15min.csv`
- `data/processed/external/clearfarm/clearfarm_health_observations.csv`
- `artifacts/external/clearfarm/clearfarm_schema_profile_report.md`

### 4.2 2단계: pen-day 통합 테이블 생성

목표: 현재 프로젝트의 돈방 단위와 맞추기 위해 pig visit 로그를 pen-day로 집계한다.

생성 feature:

| feature | 의미 |
| --- | --- |
| `daily_feed_intake_kg` | pen/day 총 섭취량 |
| `feed_visits` | pen/day 방문 횟수 |
| `mean_visit_duration_sec` | 평균 방문 시간 |
| `mean_feed_rate` | 평균 급이 속도 |
| `active_feeding_pigs` | 실제 급이한 pig 수 |
| `feed_drop_pct_1d` | 전일 대비 급이 감소율 |
| `feed_drop_pct_3d` | 3일 rolling 대비 급이 감소율 |
| `temperature_mean` | 일 평균 온도 |
| `humidity_mean` | 일 평균 습도 |
| `co2_mean`, `co2_max` | CO2 평균/최대 |
| `ammonia_mean`, `ammonia_max` | NH3 평균/최대 |
| `cough_count`, `diarrhea_count`, `pant_count` | 건강 관찰 지표 |
| `removal_event` | sickbay/출하/제거 이벤트 |

산출물:

- `data/processed/external/clearfarm/clearfarm_pen_day.csv`
- `artifacts/external/clearfarm/clearfarm_pen_day_report.md`

### 4.3 3단계: 기존 rule 외부 검증

검증할 rule:

| 기존 rule/category | ClearFarm 매핑 |
| --- | --- |
| `feed_drop` | daily feed intake 감소, active feeding pigs 감소 |
| `water_drop` | 직접 water는 없음. feeding/health와 결합한 management proxy로만 사용 |
| `environment_failure` | CO2/NH3/temperature/humidity abnormal |
| `respiratory` | cough, sneeze, pumping, panting |
| `treatment/removal` | Pig removals, sickbay 이동 |
| `heat_stress` | high temp + panting + feed drop |

산출물:

- `artifacts/external/clearfarm/clearfarm_rule_validation.csv`
- `artifacts/external/clearfarm/clearfarm_rule_validation_report.md`

### 4.4 4단계: 상반기 우선 평가

사용자 방향에 맞춰 1-5월 데이터를 우선 본다.

가능한 구간:

- Exp1: 2020-12 ~ 2021-02 중 1-2월 포함
- Exp3: 2022-05 ~ 2022-08 중 5월 포함
- Exp2/Exp4: 9-12월 위주라 비교군

작업:

1. 1-5월 pen-day만 필터링
2. feed/environment/health event 빈도 계산
3. 나머지 월과 비교
4. 프로젝트의 “상반기 우선” 전략이 데이터상 가능한지 판정

산출물:

- `artifacts/external/clearfarm/clearfarm_seasonal_availability_report.md`

## 5. RFID-LoRaWAN 세부 활용 계획

RFID 데이터는 activity baseline에 사용한다.

### 5.1 1단계: pig-hour/pig-day movement feature 생성

생성 feature:

| feature | 의미 |
| --- | --- |
| `distance_sum_hour` | 시간별 이동거리 합 |
| `distance_mean_hour` | 시간별 평균 이동거리 |
| `distance_std_hour` | 시간별 변동성 |
| `distance_sum_day` | 일별 이동거리 합 |
| `night_activity_ratio` | 야간 활동 비율 |
| `activity_drop_pct_1d` | 전일 대비 활동량 감소 |
| `activity_drop_zscore` | 개체별 정상 대비 활동량 이탈 |

산출물:

- `data/processed/external/rfid_lorawan/rfid_pig_hour.csv`
- `data/processed/external/rfid_lorawan/rfid_pig_day.csv`
- `artifacts/external/rfid_lorawan/rfid_activity_baseline_report.md`

### 5.2 2단계: activity_drop rule 후보 생성

목표:

- 개체별 이동거리의 정상 변동 범위 산정
- 하루 이동거리 급감 기준 후보 산출
- 기존 AI Hub 622 행동량 트랙과 비교

주의:

- 질병 라벨이 없으므로 recall/precision 평가는 불가
- 정상 baseline과 synthetic activity drop sanity check에 사용

## 6. 5126661 Feeding 세부 활용 계획

5126661은 시계열이 아니라 feeding feature reference로 쓴다.

### 6.1 1단계: 정상 feeding reference table 생성

작업:

1. `DFIkg_day` 분포 확인
2. `NDVvisits_day`, `FOmin_day`, `FIVg_visit`, `DUVmin_visit`, `FRg_min_day` 분포 확인
3. sex, station, body weight 기준 차이 확인
4. ClearFarm feeding feature와 단위/범위 비교

산출물:

- `artifacts/external/pig_feeding_behavior_5126661/feeding_reference_summary.csv`
- `artifacts/external/pig_feeding_behavior_5126661/feeding_reference_report.md`

### 6.2 2단계: feed_drop rule 기준 보조

활용 방식:

- 비육돈 개체당 정상 일일 사료섭취량 범위 확인
- 방문 횟수/방문 시간/방문당 섭취량 기준 확인
- ClearFarm pen-day feed_drop threshold를 정할 때 보조 근거로 사용

주의:

- row 587개 요약 데이터라 단독 anomaly detection 학습에는 부적합
- 날짜 정보가 없어 lead-time 평가에는 사용하지 않음

## 7. 전체 통합 순서

### 1순위: ClearFarm pen-day 통합

이 데이터가 가장 중요하다. feeding, climate, health observation이 같은 농장/round 안에 있어 현재 프로젝트의 management/environment 약점을 직접 보완한다.

완료 기준:

- `clearfarm_pen_day.csv` 생성
- pen/day별 feed, climate, health, removal event 포함
- 상반기 1-5월 가능성 리포트 생성

### 2순위: ClearFarm rule validation

완료 기준:

- feed_drop/environment/respiratory/removal event와 rule 후보 매핑
- 기존 domain rule 개선 후보 작성

### 3순위: RFID movement baseline

완료 기준:

- pig-hour/pig-day 이동량 baseline 생성
- activity_drop threshold 후보 생성

### 4순위: 5126661 feeding reference

완료 기준:

- 정상 feeding feature 분포표 생성
- ClearFarm feed feature와 비교

### 5순위: 기존 프로젝트 scorecard 갱신

완료 기준:

- `performance_scorecard.md`에 ClearFarm/RFID/5126661 외부 검증 섹션 추가
- 최초 기획 달성률에서 management/activity 데이터 보강률 재평가

## 8. 현재 프로젝트에 주는 의미

이번 데이터 추가로 프로젝트 방향이 더 좋아진다.

기존에는 disease 쪽은 ASFV/PRRSV로 어느 정도 근거가 생겼지만, management와 activity 쪽은 약했다. ClearFarm, RFID, 5126661을 넣으면 다음이 가능해진다.

- `feed_drop`을 실제 전자급이기 데이터로 설계
- `environment_failure`를 실제 CO2/NH3/온습도 센서로 검증
- `respiratory`를 cough/sneeze/panting 관찰값과 연결
- `activity_drop`을 RFID movement baseline으로 보강
- `sickbay/removal/slaughter` 이벤트를 운영 event로 활용
- 돈방/pen 단위 MVP의 현실성을 크게 높임

## 9. 다음 작업

바로 다음 작업은 ClearFarm의 feeding, climate, health observation을 표준화해서 `clearfarm_pen_day.csv`를 만드는 것이다. 이 테이블이 만들어지면 현재 프로젝트의 rule/lead-time/scorecard에 실제 농장 observational data를 붙일 수 있다.
