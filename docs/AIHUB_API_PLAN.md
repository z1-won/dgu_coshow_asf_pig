# AI Hub API 연동 계획

## 현재 확인된 대상

- 데이터셋: `622, 지능형 스마트축사 통합 데이터(양돈)`
- 조회 명령:

```bash
export AIHUBSHELL_BIN="/Users/bangjiwon/dev/pigproject/bin/aihubshell"
pig-aihub files --dataset-key 622
```

## 다운로드 우선순위

전체 원천 이미지는 파일 하나가 수십 GB입니다. 처음에는 라벨링데이터만 받아 정규화와 모델 입력 가능성을 검증합니다.

| 우선순위 | 구분 | 파일 | 용량 | filekey | 이유 |
| --- | --- | --- | --- | --- | --- |
| 1 | Training 라벨 | `03.키포인트/TL01.zip` | 13 MB | `533709` | 활동량 distance/keypoint 기반 모델 피처 검증 |
| 2 | Validation 라벨 | `03.키포인트/VL01.zip` | 2 MB | `533719` | 검증 데이터 구조 확인 |
| 3 | Training 라벨 | `01.바운딩박스/TL01.zip` | 148 MB | `533707` | 돈방/개체 bbox 기반 위치 분석 |
| 4 | Validation 라벨 | `01.바운딩박스/VL01.zip` | 19 MB | `533717` | bbox 검증 구조 확인 |
| 5 | 원천 이미지 | `03.키포인트/TS11.zip` | 37 GB | `533706` | 가장 작은 키포인트 원천 이미지 묶음 |

## 사용자 1회 준비

API 키를 채팅창에 붙여 넣지 말고, 터미널에서 환경변수로만 설정합니다.

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
export AIHUB_API_KEY="발급받은_키"
export AIHUBSHELL_BIN="/Users/bangjiwon/dev/pigproject/bin/aihubshell"
```

## 첫 다운로드

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

## 다운로드 후 처리

```bash
pig-normalize \
  --input-dir data/raw/aihub/622 \
  --output data/processed/aihub_622_features.csv \
  --model-output data/processed/aihub_622_model_features.csv

pig-validate-data \
  --input data/processed/aihub_622_features.csv \
  --output artifacts/aihub_622_validation_report.md
```

## 판단 기준

- JSON 파싱 성공
- `chamber_number`, `datetime`, 환경 4종 컬럼 존재
- keypoint 또는 distance 계열 컬럼 존재
- 돈방별 데이터가 시간순으로 충분히 존재
- 결측률이 높은 컬럼은 모델 입력에서 제외하거나 보간 정책 수립

## 다음 확장

1. 키포인트 라벨 구조가 샘플과 다르면 `sample_analysis.py`의 alias를 확장합니다.
2. 라벨만으로 모델 입력이 충분하면 이미지 다운로드를 미룹니다.
3. 이미지가 필요하면 가장 작은 원천 이미지 묶음부터 받아 라벨-이미지 매칭률을 검증합니다.
4. 장기 학습 전에는 chamber/date 파티션으로 CSV 또는 Parquet를 나눠 저장합니다.
