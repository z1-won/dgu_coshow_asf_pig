# 병렬 데이터 트랙 계획

## 목적

기존 `622, 지능형 스마트축사 통합 데이터(양돈)`는 활동량/keypoint/환경센서 중심의 ASF 조기 이상탐지 주 데이터로 둡니다.

추가로 `71408`, `71763` 양돈 생체 에너지 데이터를 병렬 트랙으로 수집해 체온, 열량, 대사/에너지 관련 피처를 보강합니다.

## 트랙 구성

| 트랙 | 데이터셋 | 역할 |
| --- | --- | --- |
| Smart Farm | `622` | keypoint distance, 환경센서, 돈방 단위 활동성 기반 핵심 이상탐지 |
| Bio Energy 1Y | `71408` | 양돈 생체 에너지 1차년도 라벨 구조 분석 및 보조 피처 후보 발굴 |
| Bio Energy 2Y | `71763` | 양돈 생체 에너지 2차년도 라벨 구조 분석 및 연도 간 스키마 차이 확인 |

## 첫 다운로드 순서

원천 데이터는 100GB 단위이므로 절대 먼저 받지 않습니다. 라벨링데이터와 2차년도 `Other.zip`부터 받습니다.

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
export AIHUB_API_KEY="발급받은_키"

# 622: 스마트축사 통합 데이터(양돈), keypoint label
pig-aihub download --dataset-key 622 --file-key 533709 --output-dir data/raw/aihub/622
pig-aihub download --dataset-key 622 --file-key 533719 --output-dir data/raw/aihub/622

# 71408: 양돈 생체 에너지 데이터, label
pig-aihub download --dataset-key 71408 --file-key 509489 --output-dir data/raw/aihub/71408
pig-aihub download --dataset-key 71408 --file-key 509492 --output-dir data/raw/aihub/71408

# 71763: 양돈 생체 에너지 데이터 2023, meta + label
pig-aihub download --dataset-key 71763 --file-key 528761 --output-dir data/raw/aihub/71763
pig-aihub download --dataset-key 71763 --file-key 528771 --output-dir data/raw/aihub/71763
pig-aihub download --dataset-key 71763 --file-key 528774 --output-dir data/raw/aihub/71763
```

## 다운로드 후 처리

각 데이터셋은 먼저 독립적으로 정규화/검증합니다.

```bash
pig-normalize \
  --input-dir data/raw/aihub/622 \
  --output data/processed/aihub_622_features.csv \
  --model-output data/processed/aihub_622_model_features.csv

pig-validate-data \
  --input data/processed/aihub_622_features.csv \
  --output artifacts/aihub_622_validation_report.md
```

생체 에너지 데이터는 라벨 스키마를 확인한 뒤 `normalize.py`에 별도 alias를 추가합니다. 스키마가 622와 다를 가능성이 높기 때문에, 첫 다운로드 후에는 바로 학습보다 `JSON 필드 분석 -> 정규화 컬럼 매핑 -> 품질검증` 순서로 진행합니다.

## 통합 피처 후보

| 표준 컬럼 | 622 | 71408/71763 예상 |
| --- | --- | --- |
| `chamber_number` | 돈방 번호 | 돈방/사육 구역 번호 |
| `datetime` | 측정 일자+시간+프레임 | 측정 일자+시간 |
| `T`, `RH`, `CO2`, `NH3` | 환경센서 | 환경센서가 있으면 공통 사용 |
| `distance` | keypoint 거리 | 없으면 결측 |
| `breath_rate` | 호흡수 | 있으면 공통 사용 |
| 체온 4종 | 호흡량 라벨 | 있으면 공통 사용 |
| `sensible_heat`, `latent_heat` | 일부 라벨 | 생체 에너지 핵심 후보 |
| `pig_manure`, `feedstuff_volume`, `watersupply` | 일부 라벨 | 사양/대사 보조 피처 |

## 판단 기준

- 71408/71763 라벨에서 시간축이 충분하면 LSTM 보조 피처로 통합합니다.
- 시간축이 부족하거나 집계 단위가 다르면 보고서/통계 피처로만 활용합니다.
- ASF 조기경보 모델의 핵심 입력은 우선 622 keypoint + 체온 + 환경센서로 유지합니다.
