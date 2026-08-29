# ASFV Challenge Dryad 작업 계획

작성일: 2026-08-30  
원본 위치: `/Users/bangjiwon/Downloads/doi_10_5061_dryad_cnp5hqcm5__v20260609`  
프로젝트 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/asfv_challenge_dryad`

## 1. 현재 처리 상태

다운로드된 ASFV Dryad 데이터를 프로젝트 raw 폴더로 복사했다. 원본 Downloads 폴더는 그대로 보존했다.

확인된 파일:

- CSV 파일 44개
- README 1개
- 전체 용량 약 208 KB

생성한 1차 인벤토리:

- `artifacts/external/asfv_challenge_dryad/asfv_csv_inventory.csv`
- `artifacts/external/asfv_challenge_dryad/asfv_csv_inventory_report.md`

## 2. 이 데이터셋의 역할

이 데이터는 실제 ASFV challenge 기반 데이터라 현재 프로젝트에서 가장 직접적인 외부 검증 근거다.

현재 프로젝트에서는 다음 용도로 쓴다.

1. `rectal_temp_high` rule의 ASFV 기준 threshold 검증
2. clinical score 상승 시점과 체온 상승 시점의 시간차 확인
3. viral load와 clinical/temperature의 동시성 또는 선후관계 확인
4. “ASF 확진 모델”이 아니라 “ASF 의심 조기 선별”이라는 표현의 근거 수치 보강
5. PRRSV 데이터와 비교해 질병 일반 신호와 ASF 특이 신호를 구분

주의할 점:

- 표본 수는 작다.
- 실험실 challenge 데이터이므로 상업농장 돈방 환경과 다르다.
- 사료/음수/CCTV 행동 데이터는 없다.
- 따라서 메인 LSTM 학습 데이터로 섞기보다 rule 검증과 설명 근거로 사용한다.

## 3. 핵심 파일 우선순위

| 우선순위 | 파일 | 규모 | 이유 |
| --- | --- | ---: | --- |
| 1 | `Fig._1F_-_Temperature.csv` | 29 rows, 11 cols | challenge 후 체온 변화. ASF temperature rule 핵심 |
| 2 | `Fig._1F_-_Clinical_scores.csv` | 29 rows, 11 cols | challenge 후 clinical score. target/proxy 기준 |
| 3 | `Fig._1G_-_Survival.csv` | 8 rows, 3 cols | severe outcome 확인 |
| 4 | `Fig._1H_-_Viral_loads_(blood).csv` | 5 rows, 11 cols | challenge 후 혈중 viral load |
| 5 | `Sup._Fig._4_-_Area_under_curve.csv` | 26 rows, 11 cols | clinical score AUC 보조 |
| 6 | `Sup._Fig._3_*` 혈액 지표 | 각 6 rows, 11 cols | 보조 생리/면역 지표 |
| 7 | `Fig._1B`, `Fig._1C`, `Fig._1E` | immunization phase | challenge 이전 면역/약독주 관련 배경 |

## 4. 작업 단계

### 1단계: ASFV challenge timeline 생성

목표: challenge 이후 pig_id, day_post_challenge 기준으로 temperature, clinical score, viral load를 long format으로 통합한다.

입력 파일:

- `Fig._1F_-_Temperature.csv`
- `Fig._1F_-_Clinical_scores.csv`
- `Fig._1H_-_Viral_loads_(blood).csv`
- `Fig._1G_-_Survival.csv`

표준 컬럼 후보:

| 컬럼 | 의미 |
| --- | --- |
| `pig_id` | 개체 ID |
| `pig_group` | Farm/SPF group |
| `day_post_challenge` | challenge 이후 일수 |
| `rectal_temp_c` | 직장 체온 |
| `clinical_score` | 임상 점수 |
| `viral_load_blood` | 혈중 viral load |
| `survival_event` | 폐사/생존 event |

산출물:

- `data/processed/external/asfv_challenge_dryad/asfv_challenge_timeline.csv`
- `artifacts/external/asfv_challenge_dryad/asfv_timeline_build_report.md`

### 2단계: 체온 threshold sweep

목표: ASFV challenge 기준으로 체온 rule의 민감도/특이도/정밀도를 다시 산출한다.

후보 threshold:

- 39.5 C
- 40.0 C
- 40.5 C
- 41.0 C
- 개체별 baseline 대비 +1.0 C
- 개체별 baseline 대비 +1.5 C

타깃 후보:

- clinical_score > 0
- clinical_score >= 1
- clinical_score >= 2
- survival_event 발생 전 구간

산출물:

- `artifacts/external/asfv_challenge_dryad/asfv_temperature_threshold_sweep.csv`
- `artifacts/external/asfv_challenge_dryad/asfv_temperature_threshold_report.md`

### 3단계: lead-time proxy 평가

목표: clinical score가 올라가기 전 체온 rule이 먼저 반응하는지 본다.

평가 질문:

1. clinical_score 최초 상승일보다 체온 상승이 먼저인가?
2. viral load 검출보다 체온 상승이 먼저인가?
3. 체온 rule이 너무 늦게 반응하는가?
4. 고정 threshold와 개인 baseline 대비 threshold 중 무엇이 유리한가?

산출물:

- `artifacts/external/asfv_challenge_dryad/asfv_lead_time_metrics.csv`
- `artifacts/external/asfv_challenge_dryad/asfv_lead_time_report.md`

### 4단계: 기존 ASF Dryad 분석 갱신

현재 프로젝트에는 이미 `artifacts/asf_dryad_validation/` 산출물이 있다. 이번 다운로드 데이터를 기준으로 파일 경로와 분석 결과를 재확인한다.

작업:

1. 기존 `asf_dryad_analysis.py`가 이 raw 폴더를 기준으로 읽는지 확인
2. 경로가 다르면 config/CLI 인자 보강
3. 기존 threshold sweep 결과와 이번 raw 데이터 기준 결과 비교
4. `EXTERNAL_VALIDATION_SUMMARY.md` 갱신

산출물:

- `artifacts/asf_dryad_validation/asf_dryad_validation_report.md` 갱신
- `docs/04_evaluation_validation/ASF_REAL_CHALLENGE_VALIDATION.md` 갱신
- `artifacts/performance_scorecard.md`에 반영

## 5. PRRSV 데이터와의 관계

| 데이터 | 역할 |
| --- | --- |
| ASFV Challenge Dryad | ASF 특이 체온/clinical score 외부 검증 |
| PRRSV Play Study | 실제 호흡기 질병에서 행동/사료/체온 변화 검증 |
| HotPig | heat stress와 질병성 이상의 confounder 검증 |
| SOWELL | feed/water/management rule 검증 |

ASFV는 프로젝트 목표와 가장 직접적으로 연결되지만, 행동/사료 데이터가 없다. 그래서 ASFV만으로는 전체 pipeline을 검증할 수 없고, PRRSV/SOWELL/HotPig와 함께 써야 한다.

## 6. 우선 실행 순서

1. ASFV challenge timeline 생성
2. `Fig._1F` clinical score/temperature long format 변환
3. 체온 threshold sweep 실행
4. clinical score 기준 lead-time proxy 계산
5. 기존 ASF Dryad 리포트와 성능표 갱신
6. PRRSV 분석과 비교해 “ASF 특이 근거”와 “질병 일반 근거”를 분리

## 7. 다음 작업

바로 다음 작업은 1단계 `ASFV challenge timeline 생성`이다. 이 데이터를 먼저 표준 long format으로 바꾸면, 기존 ASF Dryad threshold sweep과 lead-time 평가를 더 정확히 다시 실행할 수 있다.
