# 생체 에너지 Threshold 비교 보고

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`  
산출물 경로: `artifacts/bioenergy_split_v2`

> **업데이트 (2026-08-26, 돈방별 scaler 적용 후)**: scaler를 전체 통합 1개에서 돈방별로 바꾸고 다시 학습/탐지한 결과, p97 기준 confirmed anomaly가 **3개 → 0개**로 바뀌었습니다.
>
> | 기준 | threshold (신규) | raw anomaly | confirmed anomaly |
> | --- | ---: | ---: | ---: |
> | p95 | 2.094753 | 4 | 0 |
> | p97 | 2.104959 | 3 | 0 |
> | p99 | 2.156519 | 1 | 0 |
>
> error summary(신규): min `0.777491`, median `1.383945`, mean `1.363784`, max `2.198874`.
>
> 이전 confirmed anomaly 3개는 모두 `71408/chamber 1` 구간이었는데(아래 6절), 돈방별 scaler 적용 후에는 이 구간이 더 이상 이상 후보로 잡히지 않습니다. 아래 절차와 원래 수치는 당시 기록으로 남겨둡니다.

## 1. 작업 목적

Step 1에서 개선한 validation split을 기준으로 LSTM Autoencoder를 다시 학습하고, anomaly threshold를 p95, p97, p99로 비교했다.

목표는 현재 샘플 규모에서 너무 민감하지 않으면서도 실제 이상 후보를 확인할 수 있는 실험용 기준선을 정하는 것이다.

## 2. 입력 데이터

- 사용 데이터셋: AI Hub `71408`, `71763`
- 사용 피처: 생체 에너지 JSON에서 추출한 호흡, 체온, 거리, 환경, 열량 계열 수치 피처
- sequence length: 24
- train windows: 309
- validation windows: 71

## 3. 학습 결과

- 모델: LSTM Autoencoder
- 학습 설정: 최대 50 epoch, EarlyStopping 적용
- 실제 종료: 24 epoch
- 모델 파일:
  - `artifacts/bioenergy_split_v2/best_model.keras`
  - `artifacts/bioenergy_split_v2/final_model.keras`

## 4. Threshold 비교

| 기준 | threshold | raw anomaly windows | confirmed anomaly windows |
| --- | ---: | ---: | ---: |
| p95 | 1.454100 | 4 | 4 |
| p97 | 1.475687 | 3 | 3 |
| p99 | 1.540135 | 1 | 0 |

Error summary:

- min: 0.465506
- median: 0.966864
- mean: 0.930815
- max: 1.574011

## 5. 선택 기준

현재 실험 기준 threshold는 p97을 권장한다.

이유:

- p95는 현재 검증셋에서 다소 민감하게 반응한다.
- p97은 raw anomaly 3개와 confirmed anomaly 3개가 모두 남아 이상 후보 확인에 적합하다.
- p99는 raw anomaly 1개만 잡히고 연속 조건 적용 후 confirmed anomaly가 0개라 현재 단계에서는 너무 보수적이다.

## 6. 탐지 결과 요약

p97 기준 탐지 결과, confirmed anomaly 3개는 모두 `71408 / chamber 1` 구간에서 발생했다.

상위 anomaly window:

| dataset_key | chamber_number | start_datetime | end_datetime | reconstruction_error |
| --- | ---: | --- | --- | ---: |
| 71408 | 1 | 2022-11-17 18:02:00 | 2022-12-31 15:52:00 | 1.574011 |
| 71408 | 1 | 2022-11-17 17:21:00 | 2022-12-31 09:55:00 | 1.525616 |
| 71408 | 1 | 2022-11-17 13:59:00 | 2022-12-30 10:35:00 | 1.477763 |

주의할 점:

- 현재 window의 시작/종료 시각은 원본 JSON의 집계 timestamp 기준으로 이어진 범위다.
- 일부 센서 데이터는 시간 간격이 균일하지 않아, 실제 운영 리포트에서는 시간축 재샘플링 또는 구간 단위 해석 보정이 필요하다.
- 현재 threshold는 운영 확정값이 아니라 추가 데이터 연결 전까지의 실험 기준이다.

## 7. 생성 산출물

- `artifacts/bioenergy_split_v2/bioenergy_threshold_comparison.csv`
- `artifacts/bioenergy_split_v2/bioenergy_detection_windows.csv`
- `artifacts/bioenergy_split_v2/bioenergy_detection_report.md`
- `artifacts/bioenergy_split_v2/bioenergy_error_distribution.jpg`

## 8. 다음 작업

다음 단계는 탐지 리포트 고도화다.

- 시간순 anomaly score 그래프 추가
- 돈방별 anomaly score heatmap 추가
- threshold 비교 그래프 추가
- 정상 window와 이상 후보 window의 피처 평균 비교 추가
- 팀원이 리포트만 보고 어느 돈방, 어느 기간, 어떤 피처가 이상했는지 판단할 수 있게 개선
