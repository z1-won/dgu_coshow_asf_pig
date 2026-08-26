# Validation Split 개선 결과

작성일: 2026-08-26

> **업데이트 (2026-08-26, 돈방별 scaler 적용 후)**: 이 문서의 split 결과(window 수, train/val 분할)는 그대로 유효합니다. 다만 이후 scaler를 돈방별로 따로 학습하도록 바꾸면서 (`fit_scalers_per_chamber`, `src/pigproject/bioenergy_pipeline.py`), 이 split으로 학습한 모델의 anomaly 수치가 달라졌습니다. 최신 threshold/anomaly 결과는 [docs/THRESHOLD_COMPARISON_REPORT.md](THRESHOLD_COMPARISON_REPORT.md) 업데이트 노트를 참고하세요.

## 목적

기존 생체 에너지 LSTM 입력의 validation window가 20개뿐이고, 대부분 `71763` 데이터셋에 치우쳐 있었다. 이를 개선하기 위해 dataset/chamber별 tail validation 구간을 최소 window 수 이상 확보하도록 split 로직을 수정했다.

## 변경 내용

수정 파일:

- `/Users/bangjiwon/dev/pigproject/src/pigproject/bioenergy_pipeline.py`

주요 변경:

- `dataset_key + chamber_number` 그룹별 split summary 생성
- `seq_len`보다 짧은 그룹은 자동 제외
- 짧지만 학습/검증 window가 가능한 그룹은 tail validation을 강제로 확보
- 기본 `min_val_windows`를 10으로 설정
- split summary CSV 저장

## 실행 명령

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate

pig-build-bioenergy \
  --input data/processed/aihub_71408_features.csv \
  --input data/processed/aihub_71763_features.csv \
  --output-dir artifacts/bioenergy_split_v2 \
  --seq-len 24 \
  --min-val-windows 10
```

## 결과

- 집계 행 수: 650
- `X_train`: `(309, 24, 24)`
- `X_val`: `(71, 24, 24)`

dataset별 window 수:

| dataset | train windows | validation windows |
| --- | ---: | ---: |
| 71408 | 29 | 26 |
| 71763 | 280 | 45 |

group별 split:

| dataset | chamber | total rows | train windows | validation windows | 상태 |
| --- | ---: | ---: | ---: | ---: | --- |
| 71408 | 1 | 29 | 1 | 6 | 짧은 그룹이라 train/val overlap 사용 |
| 71408 | 2 | 73 | 17 | 10 | non-overlap |
| 71408 | 3 | 19 | 0 | 0 | `seq_len=24`보다 짧아 제외 |
| 71408 | 4 | 43 | 11 | 10 | 짧은 그룹이라 train/val overlap 사용 |
| 71763 | 1 | 188 | 127 | 15 | non-overlap |
| 71763 | 2 | 118 | 62 | 10 | non-overlap |
| 71763 | 3 | 133 | 77 | 10 | non-overlap |
| 71763 | 4 | 47 | 14 | 10 | 짧은 그룹이라 train/val overlap 사용 |

## 해석

개선 전:

- `X_val`: 20개
- validation이 `71763` 중심

개선 후:

- `X_val`: 71개
- `71408`도 validation에 26개 포함
- 목표였던 validation window 50개 이상 확보 완료

주의:

- 짧은 그룹에서는 train/val overlap이 일부 존재한다.
- 이는 현재 데이터 길이가 짧아 validation window를 확보하기 위한 임시 정책이다.
- 향후 더 긴 기간의 데이터를 받으면 overlap을 제거하는 것이 바람직하다.

## 다음 단계

개선된 split 산출물인 `artifacts/bioenergy_split_v2`를 기준으로 모델을 다시 학습한다.

권장 명령:

```bash
pig-train --artifact-dir artifacts/bioenergy_split_v2 --epochs 50 --batch-size 16
pig-detect --artifact-dir artifacts/bioenergy_split_v2 --percentile 99 --consecutive-required 3
pig-bioenergy-report --artifact-dir artifacts/bioenergy_split_v2 --seq-len 24
```
