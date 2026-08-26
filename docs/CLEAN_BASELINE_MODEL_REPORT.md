# 정제 Normal Baseline 모델 보고

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 1. 목적

현재 보유한 생체 에너지 데이터를 대부분 정상 상태로 보고, 그중 이전 모델이 유난히 튄다고 판단한 구간만 제외한 뒤 새 baseline 모델을 만들었다.

이 모델의 목적은 질병을 확정하는 것이 아니라, 앞으로 새 데이터가 들어왔을 때 기존 정상 패턴과 많이 다른 구간을 조기 이상 후보로 표시하는 것이다.

## 2. 처리 방식

진행 순서:

1. 기존 모델로 현재 데이터의 anomaly score를 계산했다.
2. p97 기준에서 confirmed anomaly로 잡힌 window 3개를 확인했다.
3. 해당 window에 포함된 원본 집계 row 26개를 정상 baseline 학습 대상에서 제외했다.
4. 남은 데이터를 정상 baseline 후보로 보고 LSTM Autoencoder를 다시 학습했다.
5. 새 모델에서 p95, p97, p99 threshold를 비교했다.
6. 운영용 실험 기준은 보수적인 p99로 설정했다.

## 3. 데이터 정제 결과

| 항목 | 값 |
| --- | ---: |
| 원본 집계 row | 650 |
| 제외 row | 26 |
| baseline 사용 row | 624 |
| 제외 기준 window | confirmed anomaly 3개 |
| 학습 window | 308 |
| 검증 window | 65 |
| 피처 수 | 24 |

제외된 구간은 이전 탐지에서 `71408 / chamber 1`의 이상 후보로 잡힌 구간이다.

## 4. 새 모델 결과

모델:

- LSTM Autoencoder
- 입력 길이: 24개 시점
- 입력 피처: 24개
- 최대 학습 epoch: 50
- EarlyStopping 적용

생성 모델:

- `artifacts/bioenergy_clean_baseline/best_model.keras`
- `artifacts/bioenergy_clean_baseline/final_model.keras`

## 5. Threshold 비교

| 기준 | threshold | raw anomaly windows | confirmed anomaly windows |
| --- | ---: | ---: | ---: |
| p95 | 1.381958 | 4 | 3 |
| p97 | 1.404550 | 2 | 0 |
| p99 | 1.424001 | 1 | 0 |

운영용 실험 기준은 p99를 권장한다.

이유:

- 현재 baseline 데이터 자체에서는 confirmed anomaly가 0개다.
- 기준이 너무 민감하면 정상 상태에서도 알림이 자주 울릴 수 있다.
- 나중에 새 데이터가 들어왔을 때 p99 기준을 넘고, 연속 3개 window 이상 유지되면 이상 후보로 볼 수 있다.

## 6. 비전문가용 해석

이번 모델은 돼지방의 평소 생체/환경 흐름을 기억해두는 모델이다.

현재 데이터에서 너무 튀는 구간은 정상 기준에서 빼고 다시 학습했기 때문에, 앞으로 새 데이터가 들어왔을 때 평소와 다른 흐름이 나타나면 더 깔끔하게 이상 후보로 표시할 수 있다.

현재 baseline 자체를 다시 검사했을 때는 최종 이상 후보가 0개다. 이는 정상 기준 모델로 쓰기에 더 적합한 상태라는 뜻이다.

## 7. 생성 산출물

- `artifacts/bioenergy_clean_baseline/bioenergy_baseline_cleaning_summary.csv`
- `artifacts/bioenergy_clean_baseline/bioenergy_baseline_screened_rows.csv`
- `artifacts/bioenergy_clean_baseline/bioenergy_threshold_comparison.csv`
- `artifacts/bioenergy_clean_baseline/bioenergy_detection_report.md`
- `artifacts/bioenergy_clean_baseline/bioenergy_error_scatter.jpg`
- `artifacts/bioenergy_clean_baseline/bioenergy_error_distribution.jpg`
- `artifacts/bioenergy_clean_baseline/best_model.keras`
- `artifacts/bioenergy_clean_baseline/final_model.keras`

## 8. 다음 연결 방식

새 데이터가 들어오면 다음 방식으로 적용한다.

1. 새 데이터를 기존 24개 피처 구조로 정규화한다.
2. baseline scaler로 같은 기준의 숫자 범위로 변환한다.
3. 24개 시점 단위 window를 만든다.
4. `best_model.keras`로 reconstruction error를 계산한다.
5. error가 p99 threshold `1.424001`을 넘는지 확인한다.
6. 연속 3개 window 이상 넘으면 이상 후보 알림으로 표시한다.

주의:

- 이 threshold는 현재 AI Hub 샘플 기반의 실험 기준이다.
- 실제 농장 데이터가 들어오면 처음 1~2주 정도는 알림 결과를 사람이 확인하면서 threshold를 다시 보정하는 것이 좋다.
