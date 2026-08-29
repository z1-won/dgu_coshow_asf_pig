# 해외 Pig Dataset 후보 및 다운로드 안내

작성일: 2026-08-30

## 판단 기준

현재 프로젝트의 가장 큰 병목은 데이터 부족이다. 따라서 해외 데이터셋은 다음 순서로 본다.

1. 현재 성능 검증에 바로 도움이 되는가
2. 돈방/개체 단위 건강 이상, 체온, 사료, 음수, 행동 중 하나 이상을 포함하는가
3. 다운로드가 실제로 가능한가
4. 팀원 YOLO 자세 detect 및 대시보드와 연결 가능한가

## 최우선 다운로드 후보

### 1. PRRSV Play Study - 질병 challenge 임상/행동/사료 데이터

- 링크: https://datadryad.org/dataset/doi:10.5061/dryad.76hdr7t55
- 크기: 약 19.32 MB
- 형식: 여러 Excel 파일
- 주요 파일:
  - `PRRSV_Play_study_Clinical_signs__rectal_temperature_and_medical_treatments.xlsx`
  - `PRRSV_Play_study_Play__exploratory__active__inactive__feeding_behaviours.xlsx`
  - `PRRSV_Play_study_Post-inoculation_average_daily_gain__feed_intake__feed_to_gain.xlsx`
  - `PRRSV_Play_study_Viral_load_RNA.xlsx`
- 포함 정보:
  - PRRSV 감염 challenge
  - rectal temperature
  - clinical signs
  - medical treatments
  - feeding behaviour
  - active/inactive behaviour
  - viral load
- 프로젝트 용도:
  - ASF는 아니지만 실제 질병 challenge 데이터라 `질병 전후 체온/행동/사료 변화` 검증에 매우 유용
  - 현재 recall이 낮은 이유를 질병 시계열 관점에서 재점검 가능
  - disease rule과 lead-time 평가 보강 가능
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/prrsv_play_study/`

### 2. HotPig - heat stress 행동/사료/환경 시계열

- 링크: https://zenodo.org/records/15608130
- 우선 받을 파일:
  - `series.zip` 약 2.6 MB
  - `weights.zip` 약 17.6 MB, 선택
  - `frames.zip` 약 621.5 MB, CV 학습용이면 선택
  - `demo.mp4` 약 4.2 GB, 후순위
- 포함 정보:
  - 24마리 개별 돼지
  - 1분 단위 16일 시계열
  - TN 9일, HS 6일, 회복 1일
  - posture/event count
  - activity label
  - feeder output 기반 평균 사료섭취량
  - 온도/습도 조건
- 프로젝트 용도:
  - 이미 일부 sanity check에 사용한 계열이지만, 원본 `series.zip`을 확보하면 행동/사료 feature를 다시 만들 수 있음
  - 고온 스트레스와 질병성 이상을 구분하는 보조 데이터로 유용
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/hotpig/`

### 3. PigLife - 생산주기 전반 CV 이미지/영상 데이터

- 링크: https://data.aifarms.org/view/piglife
- 다운로드 페이지: https://data.aifarms.org/download/piglife
- 크기: 약 16.2 GiB
- 주의:
  - 다운로드 페이지에서 이름, 이메일, 소속 입력 및 라이선스 동의가 필요
  - 연구용 라이선스 조건 확인 필요
- 포함 정보:
  - breeding, gestation, farrow, wean, nursery, growth, finish 등 생산주기 전반
  - image/video
  - object identification
  - bounding box/segmentation
  - posture/behavior labels
  - occlusion labels
- 프로젝트 용도:
  - 팀원의 YOLO 자세 detect 모델과 가장 직접적으로 연결 가능
  - 돈방 단위 이상 경보 이후 CCTV 집중 분석용 데이터로 적합
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/piglife/`

## 2순위 다운로드 후보

### 4. Data INRAE - gestating sows precision feeding database

- 링크: https://entrepot.recherche.data.gouv.fr/dataset.xhtml?persistentId=doi:10.57745/POJ8UV
- 크기:
  - 전체 ZIP 약 70.1 MB
  - `data_csv_v2.zip` 약 16.7 MB
  - `data_sql_v2.zip` 약 17.1 MB
- 포함 정보:
  - 135 sows
  - feed_visit, feed_measure, water_measure
  - environmental_measure
  - activity accelerometers
  - automatic video activity aggregated/detailed measures
  - health, performance, litter characteristics
- 프로젝트 용도:
  - 비육돈은 아니지만 사료/음수/환경/행동이 함께 있는 정돈된 relational database
  - 현재 약한 management rule, feed_drop/water_drop 설계 보강에 유용
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/inrae_sow_feeding/`

### 5. Processed Multimodal Dataset for Pig Behavior Recognition

- 링크: https://zenodo.org/records/20370059
- 크기: 약 1.1 GB
- 형식:
  - accelerometer windows
  - WAV audio
  - log-Mel spectrogram
  - behavior labels
- 포함 class:
  - lying
  - eating
  - walking
  - drinking
- 프로젝트 용도:
  - CCTV가 아닌 wearable/audio 데이터라 메인 결합은 약함
  - eating/drinking/lying 행동 분류 feature 아이디어와 보조 검증용
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/pig_multimodal_behavior/`

## 3순위 / CV 보조 후보

### 6. SwinePose

- GitHub: https://github.com/AryaanVedak/SwinePose
- Dataset: https://zenodo.org/records/19358700
- 포함 정보:
  - 3,778 annotated frames
  - 85 video clips
  - 15 keypoints
  - COCO keypoint format
  - commercial pig farms
- 프로젝트 용도:
  - 팀원 YOLO/pose 모델의 keypoint 성능 비교 또는 fine-tuning 보조
  - 질병/사료/음수 라벨은 없으므로 건강 이상 평가용은 아님
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/swinepose/`

### 7. Pig pose estimation - Mendeley Data

- 링크: https://data.mendeley.com/datasets/sn49zt6jpw/1
- 크기: 사이트에서 Download All 필요
- 포함 정보:
  - 200 images
  - COCO format keypoint labels
  - 22 keypoints
- 프로젝트 용도:
  - pose 모델 fine-tuning 소량 보조 데이터
  - 단독으로는 프로젝트 성능 개선 영향 작음
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/mendeley_pig_pose/`

## 4순위 / ASF 역학 보조 후보

### 8. Czechia ASF Laboratory Data

- 링크: https://zenodo.org/records/15296425
- 포함 정보:
  - ASF laboratory analytical results
  - domestic pigs and wild boar
  - Czechia annual ASF reporting 보조 데이터
- 프로젝트 용도:
  - 개체 행동/센서 모델에는 직접 연결 어려움
  - ASF 발생률, 지역/시기, 역학 배경 설명에 활용 가능
- 추천 저장 위치:
  - `/Users/bangjiwon/dev/pigproject/data/raw/external/asf_czechia_lab/`

### 9. WOAH WAHIS / global animal disease reports

- WAHIS: https://wahis.woah.org/
- WOAH ASF page: https://www.woah.org/en/disease/african-swine-fever/
- 보조 GitHub: https://github.com/ecohealthalliance/wahisdb
- 프로젝트 용도:
  - ASF 발생 시기/지역 배경 자료
  - 1-5월 우선 전략의 외부 근거 보강
  - 돈방 센서 모델 학습에는 직접 사용하지 않음

## 사용자에게 요청할 다운로드 우선순위

가장 먼저 받을 것:

1. PRRSV Play Study 전체 파일
2. HotPig `series.zip`
3. Data INRAE `data_csv_v2.zip`

그다음 받을 것:

4. PigLife, 단 용량 16.2 GiB와 라이선스 동의 가능할 때
5. SwinePose
6. Mendeley Pig pose estimation

후순위:

7. Czechia ASF laboratory data
8. WAHIS/ASF global reports

## 다운로드 후 내가 할 작업

사용자가 파일을 받아서 위 추천 폴더에 넣으면 다음 순서로 진행한다.

1. 파일 존재/용량/checksum 확인
2. 압축 해제
3. schema profiling
4. 현재 프로젝트 변수와 매핑
5. disease/management/environment 중 어느 rule을 보강할 수 있는지 분류
6. 상반기 1-5월 우선 분석에 쓸 수 있는 날짜 컬럼 확인
7. import script 작성
8. 성능 지표판에 외부 데이터 결과 추가
