# AI Hub API 연동 실행 가이드

이 문서는 AI Hub API 키를 발급받은 뒤, 이 프로젝트에서 실제로 데이터를 내려받고 모델 파이프라인까지 이어가는 실행 순서입니다.

중요: API 키는 채팅창이나 코드에 직접 붙여 넣지 않습니다. 로컬 `.env` 파일이나 터미널 환경변수에만 넣습니다.

## 1. 터미널에서 프로젝트 폴더로 이동

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
```

정상이라면 터미널 앞에 `(.venv)`가 표시됩니다.

## 2. API 키 설정

방법은 둘 중 하나만 사용하면 됩니다.

### 방법 A: 이번 터미널에서만 임시 설정

```bash
export AIHUB_API_KEY="여기에_발급받은_실제_API_키"
export AIHUBSHELL_BIN="/Users/bangjiwon/dev/pigproject/bin/aihubshell"
```

이 방식은 터미널을 닫으면 설정이 사라집니다. 가장 안전하고 간단합니다.

### 방법 B: `.env` 파일로 저장

```bash
cp .env.example .env
```

그 다음 `.env` 파일을 열어서 아래 줄만 실제 키로 바꿉니다.

```bash
AIHUB_API_KEY=여기에_발급받은_실제_API_키
AIHUBSHELL_BIN=/Users/bangjiwon/dev/pigproject/bin/aihubshell
```

주의: `.env` 파일은 개인 키가 들어가는 파일입니다. 공유하거나 Git에 올리면 안 됩니다.

현재 프로젝트의 Python 코드가 `.env`를 자동으로 읽는 구조는 아닙니다. `.env` 방식을 쓰는 경우에는 실행 전 아래 명령으로 현재 터미널에 불러옵니다.

```bash
set -a
source .env
set +a
```

## 3. API 키가 적용됐는지 확인

키 전체를 출력하면 안 됩니다. 아래처럼 존재 여부만 확인합니다.

```bash
python - <<'PY'
import os
print("AIHUB_API_KEY set:", bool(os.environ.get("AIHUB_API_KEY")))
print("AIHUBSHELL_BIN:", os.environ.get("AIHUBSHELL_BIN"))
PY
```

정상 예시는 다음과 같습니다.

```text
AIHUB_API_KEY set: True
AIHUBSHELL_BIN: /Users/bangjiwon/dev/pigproject/bin/aihubshell
```

## 4. AI Hub 데이터셋 목록 조회

```bash
pig-aihub list
```

목록이 길게 나오면 API 연결 자체는 동작하는 것입니다.

현재 프로젝트에서 우선 사용하는 데이터셋은 다음입니다.

```text
622: 지능형 스마트축사 통합 데이터(양돈)
71471: 소(한우, 젖소) 및 돼지 발정행동 데이터
```

## 5. 데이터셋 622의 파일 목록 조회

```bash
pig-aihub files --dataset-key 622
```

여기서 `filekey`를 확인합니다. 이미 이 프로젝트에서 먼저 사용한 키포인트 라벨 파일은 다음 두 개입니다.

- Training 키포인트 라벨: `533709`
- Validation 키포인트 라벨: `533719`

## 6. 추천 다운로드 목록 확인

```bash
pig-aihub recommended --dataset-key 622
```

현재 우선순위는 작은 라벨 파일부터 받는 것입니다. 원천 이미지는 수십 GB라서 바로 받지 않습니다.

## 7. 키포인트 라벨 다운로드

이미 받은 적이 있어도 같은 위치에 다시 받으면 파일 존재 여부를 확인할 수 있습니다.

```bash
pig-aihub download \
  --dataset-key 622 \
  --file-key 533709 \
  --output-dir data/raw/aihub/622

pig-aihub download \
  --dataset-key 622 \
  --file-key 533719 \
  --output-dir data/raw/aihub/622
```

다운로드 후 확인:

```bash
find data/raw/aihub/622 -maxdepth 5 -type f | sort
```

정상이라면 `TL01.zip`, `VL01.zip` 같은 파일이 보여야 합니다.

## 8. 다운로드한 라벨을 모델용 CSV로 변환

```bash
pig-normalize \
  --input-dir data/raw/aihub/622 \
  --output data/processed/aihub_622_keypoint_features.csv \
  --model-output data/processed/aihub_622_keypoint_model_features.csv
```

생성되는 핵심 파일:

- `data/processed/aihub_622_keypoint_features.csv`
- `data/processed/aihub_622_keypoint_model_features.csv`
- `artifacts/aihub_622_keypoint_validation_report.md`

## 9. 프레임 단위 활동 특징 생성

```bash
pig-build-activity \
  --input data/processed/aihub_622_keypoint_features.csv \
  --output data/processed/aihub_622_activity_features.csv \
  --report artifacts/aihub_622_activity_feature_report.md \
  --chunksize 100000
```

이 단계에서는 돼지 행동 라벨과 위치 정보를 이용해 프레임별 활동량 feature를 만듭니다.

## 10. 10분 단위 시계열로 변환

```bash
pig-resample-activity \
  --input data/processed/aihub_622_activity_features.csv \
  --output data/processed/aihub_622_activity_timeseries_10min.csv \
  --report artifacts/aihub_622_activity_timeseries_10min_report.md \
  --freq 10min
```

모델은 프레임 하나하나보다 시간 흐름을 봐야 하므로 10분 단위로 묶습니다.

## 11. 모델 입력 데이터 생성

```bash
pig-build-activity-model \
  --input data/processed/aihub_622_activity_timeseries_10min.csv \
  --output-dir artifacts/activity_model_10min \
  --seq-len 24
```

`seq-len 24`는 10분 단위 데이터 24개, 즉 약 4시간짜리 행동 흐름을 하나의 입력으로 본다는 뜻입니다.

## 12. 모델 학습

처음 학습:

```bash
pig-train \
  --artifact-dir artifacts/activity_model_10min \
  --epochs 30 \
  --batch-size 16
```

추가 학습:

```bash
pig-train \
  --artifact-dir artifacts/activity_model_10min \
  --resume-model best_model.keras \
  --epochs 30 \
  --batch-size 16
```

학습 후 주요 모델 파일:

- `artifacts/activity_model_10min/best_model.keras`
- `artifacts/activity_model_10min/final_model.keras`
- `artifacts/activity_model_10min/continued_model.keras`

## 13. 이상 탐지 실행

```bash
pig-detect \
  --artifact-dir artifacts/activity_model_10min \
  --percentile 99 \
  --consecutive-required 3
```

현재 기준은 상위 1% 수준으로 튀는 구간을 원시 이상 후보로 보고, 3개 구간 이상 연속될 때만 확정 이상으로 봅니다.

## 14. 결과 확인

최신 결과 보고서:

```bash
cat artifacts/activity_model_10min/lstm_detection_report.md
```

검증 결과 CSV:

```bash
open artifacts/activity_model_10min/lstm_val_results.csv
```

프로젝트를 모르는 사람에게 설명할 때는 아래 문서를 먼저 보여주면 됩니다.

```bash
open ../00_overview/MODEL_EXPLANATION_FOR_NEWCOMERS.md
```

## 15. 71471 발정행동 데이터 확인

71471은 ASF 데이터가 아니라 행동 변화 보강 후보입니다. 원천 이미지/영상보다 라벨과 메타데이터부터 확인합니다.

```bash
pig-aihub recommended --dataset-key 71471
bash scripts/inspect_aihub_71471.sh
```

`artifacts/aihub_71471_file_tree.txt`에서 돼지 라벨/메타데이터에 해당하는 작은 파일의 `filekey`를 고른 뒤 다운로드합니다.

```bash
bash scripts/download_aihub_71471_labels.sh
```

다운로드 후에는 라벨 스키마를 보고 `pig-normalize`에 71471 전용 매핑을 추가할지 결정합니다.

## 16. 문제가 생겼을 때

### `AIHUB_API_KEY is not set`

API 키 환경변수가 설정되지 않은 상태입니다.

```bash
export AIHUB_API_KEY="여기에_발급받은_실제_API_키"
```

또는 `.env`를 쓴다면:

```bash
set -a
source .env
set +a
```

### `aihubshell executable was not found`

AI Hub 다운로드 실행 파일 위치를 찾지 못한 상태입니다.

```bash
export AIHUBSHELL_BIN="/Users/bangjiwon/dev/pigproject/bin/aihubshell"
```

실행 권한 확인:

```bash
ls -l /Users/bangjiwon/dev/pigproject/bin/aihubshell
```

권한에 `x`가 없으면:

```bash
chmod +x /Users/bangjiwon/dev/pigproject/bin/aihubshell
```

### 다운로드가 너무 오래 걸림

원천 이미지 파일은 수십 GB일 수 있습니다. 먼저 라벨 파일만 받아서 모델 파이프라인을 검증하고, 이미지가 꼭 필요할 때만 가장 작은 원천 이미지 묶음부터 받습니다.

## 16. 지금 사용자가 직접 해야 하는 것

현재 사용자가 해야 하는 일은 한 가지입니다.

1. 터미널에서 프로젝트 폴더로 이동합니다.
2. 가상환경을 켭니다.
3. `AIHUB_API_KEY`에 실제 발급 키를 설정합니다.
4. `pig-aihub list`가 되는지 확인합니다.

여기까지 성공하면 이후 다운로드, 변환, 학습, 탐지는 모두 위 명령어 순서대로 진행하면 됩니다.
