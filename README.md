# PigProject

돈방 단위 돼지 활동량 및 체온 기반 이상탐지 프로젝트입니다.

목표는 ASF 확진이 아니라, 정상 패턴에서 벗어나는 돈방을 조기 선별하는 것입니다. 정상 데이터만으로 모델을 학습하고 재구성 오차 또는 One-Class 점수를 이용해 경보 후보를 찾습니다.

## 포함된 파이프라인

- `pig-preprocess`: AI Hub JSON을 읽어 돈방별 시계열 피처로 변환하고 LSTM 입력 윈도우 생성
- `pig-iforest`: 빠른 검증용 Isolation Forest baseline
- `pig-train`: LSTM Autoencoder 학습
- `pig-detect`: validation 오차 분포 기반 threshold 산정 및 이상탐지
- `pig-analyze-sample`: AI Hub 샘플 폴더 분석, 돼지 위치 맵 JPG 및 보고서 생성
- `pig-aihub`: AI Hub 공식 `aihubshell` 래퍼
- `pig-normalize`: 샘플/AI Hub 다운로드 폴더를 공통 feature CSV로 정규화
- `pig-validate-data`: 정규화 CSV 품질 검증 보고서 생성
- `pig-build-bioenergy`: 71408/71763 생체 에너지 CSV를 LSTM 입력 배열로 변환
- `pig-bioenergy-report`: 생체 에너지 탐지 결과 리포트와 오차 분포 JPG 생성
- `pig-threshold-compare`: p95/p97/p99 등 threshold 후보 비교
- `pig-build-activity`: 키포인트 라벨을 프레임 단위 행동량 feature로 집계
- `pig-resample-activity`: 프레임 단위 행동량 feature를 5분/10분 단위 시계열로 리샘플링
- `pig-build-activity-model`: 행동량 시계열을 scaler와 LSTM 입력 배열로 변환

## 설치

```bash
cd /Users/bangjiwon/dev/pigproject
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

TensorFlow 설치가 오래 걸리면 먼저 전처리와 baseline만 확인해도 됩니다.

## 빠른 실행

```bash
pig-preprocess --json-dir /path/to/normal_json --output-dir artifacts --max-files 1000
pig-iforest --artifact-dir artifacts
pig-train --artifact-dir artifacts --epochs 30
pig-detect --artifact-dir artifacts --percentile 99 --consecutive-required 3
```

샘플 데이터로 먼저 전체 흐름을 확인하려면:

```bash
pig-make-sample --output-dir data/sample_json --chambers 2 --days 4
pig-preprocess --json-dir data/sample_json --output-dir artifacts/sample --seq-len 24
pig-iforest --artifact-dir artifacts/sample
pig-train --artifact-dir artifacts/sample --epochs 1 --batch-size 16
pig-detect --artifact-dir artifacts/sample --percentile 99 --consecutive-required 3
```

제공받은 AI Hub 샘플 폴더를 분석하려면:

```bash
pig-analyze-sample --sample-dir /Users/bangjiwon/Downloads/Sample --output-dir artifacts/sample_analysis
```

AI Hub 연동 준비:

```bash
cp .env.example .env
# .env에는 실제 키를 적되 git에 올리지 않습니다.
export AIHUB_API_KEY="발급받은_키"
export AIHUBSHELL_BIN="/Users/bangjiwon/dev/pigproject/bin/aihubshell"

pig-aihub list
pig-aihub files --dataset-key 데이터셋키
pig-aihub recommended
pig-aihub download --dataset-key 데이터셋키 --file-key 파일키 --output-dir data/raw/aihub
```

양돈 주 데이터셋은 `622`입니다. 병렬 보조 트랙으로 `71408`, `71763` 양돈 생체 에너지 데이터도 함께 관리합니다. 처음에는 수십 GB 원천 이미지보다 작은 라벨 파일부터 받는 것을 권장합니다.

- 주 데이터 계획: [docs/AIHUB_API_PLAN.md](docs/AIHUB_API_PLAN.md)
- 병렬 데이터 트랙: [docs/PARALLEL_DATA_TRACKS.md](docs/PARALLEL_DATA_TRACKS.md)
- 데이터셋 매니페스트: [config/aihub_datasets.json](config/aihub_datasets.json)

다운로드 또는 샘플 폴더를 모델용 CSV로 정규화하려면:

```bash
pig-normalize \
  --input-dir /Users/bangjiwon/Downloads/Sample \
  --output data/processed/sample_features.csv \
  --model-output data/processed/sample_model_features.csv

pig-validate-data \
  --input data/processed/sample_features.csv \
  --output artifacts/sample_data_validation_report.md
```

생체 에너지 라벨을 LSTM 입력 배열로 만들려면:

```bash
pig-build-bioenergy \
  --input data/processed/aihub_71408_features.csv \
  --input data/processed/aihub_71763_features.csv \
  --output-dir artifacts/bioenergy \
  --seq-len 24 \
  --min-val-windows 10
```

학습/탐지 후 리포트를 만들려면:

```bash
pig-bioenergy-report --artifact-dir artifacts/bioenergy --seq-len 24
```

threshold 후보를 비교하려면:

```bash
pig-threshold-compare \
  --artifact-dir artifacts/bioenergy \
  --percentiles 95 97 99 \
  --consecutive-required 3
```

키포인트 XML 라벨에서 행동량 feature를 만들려면:

```bash
pig-build-activity \
  --input data/processed/aihub_622_keypoint_features.csv \
  --output data/processed/aihub_622_activity_features.csv \
  --report artifacts/aihub_622_activity_feature_report.md
```

행동량 feature를 10분 단위 시계열로 묶으려면:

```bash
pig-resample-activity \
  --input data/processed/aihub_622_activity_features.csv \
  --output data/processed/aihub_622_activity_timeseries_10min.csv \
  --report artifacts/aihub_622_activity_timeseries_10min_report.md \
  --freq 10min
```

행동량 시계열을 모델 입력 배열로 만들려면:

```bash
pig-build-activity-model \
  --input data/processed/aihub_622_activity_timeseries_10min.csv \
  --output-dir artifacts/activity_model_10min \
  --seq-len 24
```

처음에는 전체 983GB를 바로 처리하지 말고, 돈방 1~2개와 며칠치 데이터로 `--max-files`를 걸어 파이프라인을 검증하는 흐름을 권장합니다.

## 주요 피처

- 체온: `rectal_temperature`, `back_temperature`, `neck_temperature`, `head_temperature`
- 환경: `T`, `RH`, `CO2`, `NH3`
- 활동/호흡: `distance`, `breath_rate`
- 사양관리: `ventilation_rate`, `feedstuff_volume`, `watersupply`

전처리 로더는 AI Hub JSON 필드명이 `-` 또는 `_`로 조금 다를 수 있는 상황을 고려해 alias 기반으로 값을 찾습니다.

## 산출물

- `artifacts/X_train.npy`
- `artifacts/X_val.npy`
- `artifacts/scaler.joblib`
- `artifacts/best_model.keras`
- `artifacts/final_model.keras`
- `artifacts/threshold.npy`
- `artifacts/last_errors.npy`
- `artifacts/last_raw_flags.npy`
- `artifacts/last_confirmed_flags.npy`
