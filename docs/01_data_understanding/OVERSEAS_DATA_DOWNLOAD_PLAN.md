# 해외 Pig Dataset 다운로드 계획

작성일: 2026-08-30

## 1. 목표

현재 프로젝트의 가장 큰 병목은 데이터 부족이다. 특히 다음 데이터가 부족하다.

- 실제 질병 challenge에서 시간에 따라 변하는 체온/임상증상/행동/사료 데이터
- feed_drop, water_drop, treatment, environment_failure 같은 management/event 검증 데이터
- 팀원 YOLO 자세 detect 모델과 연결할 수 있는 이미지/영상/pose 데이터
- 1-5월 상반기 중심 분석에 쓸 수 있는 날짜/시점 정보

따라서 다운로드는 “작고 바로 쓸 수 있는 질병/시계열 데이터”를 먼저 받고, 큰 CV 데이터는 그 다음에 받는다.

## 2. 다운로드 우선순위

| 우선순위 | 데이터셋 | 먼저 받을 파일 | 예상 용량 | 저장 위치 | 목적 |
| --- | --- | --- | ---: | --- | --- |
| 1 | PRRSV Disease Resilience Dataset | 전체 Dryad 파일 | 19.32 MB | `data/raw/external/prrsv_play_study/` | 실제 감염 challenge 기반 체온/임상/행동/사료 변화 검증 |
| 2 | ASFV Challenge Dataset | 전체 Dryad CSV 파일 | 85.89 KB | `data/raw/external/asfv_challenge_dryad/` | ASF 체온/clinical score 외부 검증 강화 |
| 3 | SOWELL Pig Dataset | `sowell.csv.zip`, 가능하면 `Metadata.pdf` | 22.5 MB + 701.7 KB | `data/raw/external/sowell/` | feed/water/activity/environment management rule 보강 |
| 4 | HotPig | `series.zip`, `metadata.txt` | 2.6 MB + 1.1 KB | `data/raw/external/hotpig/` | heat stress 행동/사료/환경 시계열 검증 |
| 5 | Pig Multimodal Behavior Dataset | `pig_multimodal_behavior_dataset_v1.zip`, SHA256 파일 | 1.1 GB | `data/raw/external/pig_multimodal_behavior/` | lying/eating/walking/drinking 행동 보조 모델 검증 |
| 6 | PigLife | 전체 다운로드 | 16.2 GiB | `data/raw/external/piglife/` | 팀원 YOLO/CV 대시보드 연동용 이미지/영상/행동 라벨 |
| 7 | SwinePose | `SwinePose_v1.0.zip`, README | 606.8 MB | `data/raw/external/swinepose/` | pose/keypoint 모델 평가 및 fine-tuning 보조 |
| 8 | Mendeley Pig Pose | Download All | 미확인, 소형 예상 | `data/raw/external/mendeley_pig_pose/` | 200장 COCO keypoint 보조 데이터 |

## 3. 1차 다운로드 묶음

처음에는 아래 4개만 받는다. 이유는 용량이 작고 현재 성능 검증에 바로 연결되기 때문이다.

1. PRRSV Disease Resilience Dataset
2. ASFV Challenge Dataset
3. SOWELL `sowell.csv.zip` + `Metadata.pdf`
4. HotPig `series.zip` + `metadata.txt`

이 4개를 받으면 바로 할 수 있는 작업:

- PRRSV 기준 질병 전후 체온/행동/사료 변화 분석
- ASFV 기준 clinical score/temperature rule 재검증
- SOWELL 기준 feed/water/activity/environment rule 후보 생성
- HotPig 기준 heat stress와 질병성 이상 구분 보조 검증
- 현재 scorecard에 외부 데이터 수치 추가

## 4. 2차 다운로드 묶음

1차 분석이 끝난 뒤 아래를 받는다.

1. Pig Multimodal Behavior Dataset
2. SwinePose
3. Mendeley Pig Pose
4. PigLife

이 묶음은 팀원의 CV/YOLO 모델과 결합할 때 중요하다. 단, PigLife는 16.2 GiB라 용량과 라이선스 동의가 먼저 해결되어야 한다.

## 5. 사용자 다운로드 안내

### 5.1 PRRSV Disease Resilience Dataset

- 링크: https://datadryad.org/dataset/doi:10.5061/dryad.76hdr7t55
- 받을 것: Download full dataset 또는 개별 Excel 전체
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/prrsv_play_study/`

중요 파일:

- `PRRSV_Play_study_Clinical_signs__rectal_temperature_and_medical_treatments.xlsx`
- `PRRSV_Play_study_Play__exploratory__active__inactive__feeding_behaviours.xlsx`
- `PRRSV_Play_study_Post-inoculation_average_daily_gain__feed_intake__feed_to_gain.xlsx`
- `PRRSV_Play_study_Viral_load_RNA.xlsx`
- `README.md`

### 5.2 ASFV Challenge Dataset

- 링크: https://datadryad.org/dataset/doi:10.5061/dryad.cnp5hqcm5
- 받을 것: Download full dataset 또는 CSV 전체
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/asfv_challenge_dryad/`

중요 파일:

- `Fig._1B_-_clinical_scores.csv`
- `Fig._1B_-_Temperature.csv`
- `Fig._1C_-_Viral_loads_(blood).csv`
- `Fig._1F_-_Clinical_scores.csv`
- `Fig._1F_-_Temperature.csv`
- `Fig._1G_-_Survival.csv`

### 5.3 SOWELL Pig Dataset

- 링크: https://doi.org/10.57745/ER4WOJ
- 받을 것:
  - `Metadata.pdf`
  - `sowell.csv.zip`
  - 선택: `sowell.sql.zip`
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/sowell/`

우선 CSV ZIP만 있으면 분석을 시작할 수 있다. SQL ZIP은 관계형 DB로 재구성할 때 필요하다.

### 5.4 HotPig

- 링크: https://zenodo.org/records/17090997
- 받을 것:
  - `series.zip`
  - `metadata.txt`
  - 선택: `weights.zip`
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/hotpig/`

후순위 대용량 파일:

- `frames.zip`: 621.5 MB, CV frame 분석용
- `excerpt.mp4`: 82.2 MB, 영상 샘플 확인용
- `demo.mp4`: 4.2 GB, 지금은 후순위

### 5.5 Pig Multimodal Behavior Dataset

- 링크: https://zenodo.org/records/20370059
- 받을 것:
  - `pig_multimodal_behavior_dataset_v1.zip`
  - `pig_multimodal_behavior_dataset_v1_SHA256.txt`
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/pig_multimodal_behavior/`

### 5.6 PigLife

- 링크: https://data.aifarms.org/view/piglife
- 다운로드 페이지: https://data.aifarms.org/download/piglife
- 받을 것: 전체 다운로드
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/piglife/`

주의:

- 이름, 이메일, 소속 입력 및 라이선스 동의가 필요할 수 있다.
- 용량이 16.2 GiB라 디스크 여유 공간을 먼저 확인한다.

### 5.7 SwinePose

- 링크: https://zenodo.org/records/19358700
- GitHub: https://github.com/AryaanVedak/SwinePose
- 받을 것:
  - `SwinePose_v1.0.zip`
  - `README.md`
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/swinepose/`

### 5.8 Mendeley Pig Pose

- 링크: https://data.mendeley.com/datasets/sn49zt6jpw/1
- 받을 것: Download All
- 저장 위치: `/Users/bangjiwon/dev/pigproject/data/raw/external/mendeley_pig_pose/`

## 6. 다운로드 후 처리 계획

사용자가 파일을 넣어주면 다음 순서로 진행한다.

### 6.1 파일 검증

- 파일 존재 확인
- 용량 확인
- ZIP 무결성 확인
- SHA256/MD5가 제공된 경우 checksum 비교

산출물:

- `artifacts/external_data_inventory.csv`
- `artifacts/external_data_inventory_report.md`

### 6.2 스키마 프로파일링

- 파일별 row 수, column 수 확인
- 날짜/시간 컬럼 확인
- pig_id, pen_id, chamber_id에 해당하는 식별자 확인
- 질병/행동/사료/음수/환경 변수 분류

산출물:

- `artifacts/external_schema_profile.csv`
- `artifacts/external_schema_profile_report.md`

### 6.3 현재 프로젝트 변수와 매핑

| 현재 프로젝트 축 | 외부 데이터 매핑 후보 |
| --- | --- |
| disease | PRRSV clinical signs, ASFV clinical score, rectal temperature, viral load |
| management | SOWELL feed/water, PRRSV feed intake, HotPig feeder output |
| environment | SOWELL hot/cold events, HotPig heat stress temperature/humidity |
| behavior | PRRSV play/active/inactive/feeding, HotPig posture/event labels, multimodal behavior labels |
| CV/pose | PigLife, SwinePose, Mendeley Pig Pose |

산출물:

- `artifacts/external_to_project_variable_map.csv`
- `docs/01_data_understanding/EXTERNAL_DATA_MAPPING.md`

### 6.4 성능 재평가

외부 데이터 추가 후 성능표를 다시 만든다.

- LSTM 단독 sanity check
- disease rule precision/recall
- feed_drop/water_drop rule 후보 평가
- heat stress false positive 점검
- CV/pose 데이터와 dashboard 연결 가능성 평가

산출물:

- `artifacts/performance_scorecard.md`
- `artifacts/external_validation_expanded_report.md`

## 7. 결론

지금은 PRRSV, ASFV, SOWELL, HotPig 4개를 먼저 받는 것이 맞다. 이 조합은 용량이 작고, 현재 프로젝트의 약점인 질병 ground-truth 부족, management rule 부족, heat stress 구분 문제를 가장 빠르게 보완한다.

CV/YOLO 쪽은 PigLife, SwinePose, Mendeley Pig Pose를 2차로 받는다. 이 데이터들은 돈방 이상 경보 이후 개별 돼지 localization과 자세 근거 표시를 붙이는 단계에서 사용한다.
