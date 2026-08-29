# PRRSV Play Study 작업 계획

작성일: 2026-08-30  
원본 위치: `/Users/bangjiwon/Downloads/doi_10_5061_dryad_76hdr7t55__v20240914`  
프로젝트 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/prrsv_play_study`

## 1. 현재 처리 상태

다운로드된 PRRSV Dryad 데이터를 프로젝트 raw 폴더로 복사했다. 원본 Downloads 폴더는 그대로 보존했다.

확인된 파일:

- Excel 파일 8개
- README 1개
- 전체 용량 약 18 MB
- 시트 총 26개

생성한 1차 인벤토리:

- `artifacts/external/prrsv_play_study/prrsv_sheet_inventory.csv`
- `artifacts/external/prrsv_play_study/prrsv_sheet_inventory_report.md`

## 2. 이 데이터셋의 역할

이 데이터는 ASF 데이터는 아니지만 실제 PRRSV 감염 challenge 데이터다. 그래서 현재 프로젝트에서는 다음 용도로 쓴다.

1. 실제 질병 상태에서 체온, 임상증상, 행동, 사료섭취가 어떻게 변하는지 확인
2. 현재 `rectal_temp_high`, `feed_drop`, `activity_drop`, `respiratory` rule의 외부 검증
3. 질병 발생 기준일인 DPI(day post-inoculation)를 기준으로 lead-time 평가 방식 보강
4. 돈방 단위 모델이 나중에 개별 돼지/pen 단위 데이터와 결합될 수 있는지 확인

주의할 점:

- PRRSV는 ASF가 아니므로 ASF 확진 성능으로 주장하면 안 된다.
- 이 데이터는 pig-level challenge 데이터이고, 현재 메인 모델은 chamber-level 시계열이다.
- 따라서 직접 학습 데이터로 섞기보다 외부 검증/규칙 보정/feature 근거로 먼저 쓴다.

## 3. 핵심 시트 우선순위

| 우선순위 | 파일/시트 | 현재 확인 규모 | 이유 |
| --- | --- | ---: | --- |
| 1 | `Clinical signs probability` | 902 rows, 47 cols | DPI별 clinical sign이 가장 풍부함 |
| 2 | `Rectal temperature` | 232 rows, 18 cols | disease/temperature rule 검증 핵심 |
| 3 | `Active Inactive Feeding behav` | 170 rows, 36 cols | 행동 변화와 feeding 행동 검증 |
| 4 | `Feedgain_feed intake` / `Feedintake calculations` | 29/38 rows | feed intake 변화 검증 |
| 5 | `medical treatments - detailed` | 21 rows | 치료 시점과 lead-time 평가 기준 후보 |
| 6 | `long stata final log10` | 211 rows, 13 cols | viral load 기준 질병 강도/시점 확인 |
| 7 | `Skin lesions long format` | 182 rows, 23 cols | 보조 clinical/복지 지표 |
| 8 | immune/lung/preweaning 시트 | 보조 | 모델 성능보다는 해석/배경용 |

## 4. 작업 단계

### 1단계: 스키마 정리

목표: 각 핵심 시트의 실제 header row, id 컬럼, DPI 컬럼, target 후보를 확정한다.

작업:

1. Excel 시트별 header 구조 확인
2. `pigid`, `pen`, `trt`, `dpi` 표준 컬럼명 매핑
3. 결측 표기 `null`, `na` 처리 규칙 정의
4. long-format으로 읽을 시트와 wide-format으로 유지할 시트 구분

산출물:

- `artifacts/external/prrsv_play_study/prrsv_schema_profile.csv`
- `artifacts/external/prrsv_play_study/prrsv_schema_profile_report.md`

### 2단계: 질병 타임라인 테이블 생성

목표: pig_id, pen_id, dpi 기준으로 체온/임상증상/행동/사료/viral load를 하나의 long table로 만든다.

표준 테이블 후보:

| 컬럼 | 의미 |
| --- | --- |
| `pig_id` | 개체 ID |
| `pen_id` | pen/group 정보 |
| `treatment` | control/play/sentinel |
| `dpi` | 감염 후 경과일 |
| `rectal_temp_c` | 직장 체온 |
| `clinical_score` | 임상증상 종합 점수 후보 |
| `respiratory_score` | 호흡 이상 점수 |
| `cough_score` | 기침 점수 |
| `appetite_score` | 식욕 점수 |
| `active_value` | 활동 지표 후보 |
| `inactive_value` | 비활동 지표 후보 |
| `feeding_behavior` | 섭식 행동 지표 후보 |
| `feed_intake` | 사료섭취량 후보 |
| `viral_load_log10` | viral load |
| `treated` | 치료 여부 |

산출물:

- `data/processed/external/prrsv_play_study/prrsv_daily_timeline.csv`
- `artifacts/external/prrsv_play_study/prrsv_timeline_build_report.md`

### 3단계: 현재 프로젝트 rule과 매핑

목표: PRRSV 변수로 현재 rule을 외부 검증한다.

| 현재 rule/category | PRRSV 매핑 후보 |
| --- | --- |
| `rectal_temp_high` | `rectal_temp_c` |
| `respiratory` | respiratory rate score, cough score |
| `feed_drop` | feed intake, feeding behaviour |
| `activity_drop` | active/inactive behaviour |
| `treatment` | medical treatment detailed |
| disease severity | clinical score, viral load, lung lesions |

산출물:

- `artifacts/external/prrsv_play_study/prrsv_rule_mapping.csv`
- `docs/04_evaluation_validation/PRRSV_EXTERNAL_VALIDATION_PLAN.md`

### 4단계: 외부 검증 수치 산출

목표: 지금 프로젝트의 성능표에 들어갈 숫자를 만든다.

평가할 지표:

1. 체온 threshold별 sensitivity/specificity/precision
2. clinical sign 발생 전후 feed/activity 변화율
3. DPI 0 이후 며칠째 이상 신호가 나타나는지
4. treatment 시점 대비 선행 경보 가능성
5. viral load 상승과 체온/행동 변화의 시간차

산출물:

- `artifacts/external/prrsv_play_study/prrsv_temperature_threshold_sweep.csv`
- `artifacts/external/prrsv_play_study/prrsv_lead_time_metrics.csv`
- `artifacts/external/prrsv_play_study/prrsv_external_validation_report.md`

### 5단계: 프로젝트 scorecard 반영

목표: 현재 성능표에 PRRSV 검증 결과를 추가한다.

반영 방식:

- ASFV Dryad: ASF에 가까운 온도/clinical 검증
- PRRSV Play Study: 실제 호흡기 질병 challenge에서 체온/행동/사료 변화 검증
- HotPig: heat stress confounder 검증
- SOWELL: management/feed/water rule 검증

산출물:

- `artifacts/performance_scorecard.md` 갱신
- `docs/04_evaluation_validation/EXTERNAL_VALIDATION_SUMMARY.md` 갱신

## 5. 우선 실행 순서

1. PRRSV schema profile 생성
2. `Rectal temperature`와 `Clinical signs probability`부터 표준화
3. pig_id + dpi 기준 daily disease timeline 초안 생성
4. 체온 threshold sweep 실행
5. clinical score 기준 lead-time proxy 산출
6. feed/activity 시트 결합
7. 최종 PRRSV external validation report 작성

## 6. 기대 효과

이 데이터가 들어오면 지금 프로젝트에서 가장 약했던 부분을 보강할 수 있다.

- 단순 합성 이벤트가 아니라 실제 감염 challenge 기준으로 평가 가능
- 체온 rule의 민감도/정밀도 근거 보강
- `feed_drop`, `activity_drop`, `respiratory` rule의 실제 질병 연관성 확인
- YOLO 행동 feature가 어떤 방향으로 들어와야 하는지 근거 확보
- “ASF 확진”이 아니라 “질병성 이상징후 조기 선별”이라는 프로젝트 포지션을 더 설득력 있게 설명 가능

## 7. 다음 작업

바로 다음 작업은 1단계 `PRRSV schema profile 생성`이다. 이 단계에서 각 시트의 header row와 핵심 컬럼을 확정한 뒤, `Rectal temperature`와 `Clinical signs probability`를 먼저 표준화한다.
