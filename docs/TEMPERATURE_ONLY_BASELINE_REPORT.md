# 온도 전용 Baseline 모델 보고

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`  
참고자료: `/Users/bangjiwon/Downloads/1020210047517.pdf`

> **업데이트 (2026-08-26, 돈방별 scaler 적용 후)**: 돈방별 scaler로 다시 실행한 결과 `excluded_rows: 0`(이전 26), `p99 threshold: 2.718018`(이전 `1.766111`)로 바뀌었습니다. raw anomaly 1개, confirmed anomaly 0개는 동일합니다. 또한 `bioenergy_pca_cluster_scatter.jpg`(전체 24피처 기준, train+val 포함)를 다시 보면 `71763/chamber 1`의 `2023-08-09 04:37~14:25` 구간이 train 구간 안에서 3개 연속으로 threshold를 넘는 진짜 confirmed anomaly로 나타납니다 — 이 구간은 `pig-detect`가 기본적으로 validation만 검사하기 때문에 공식 지표(raw=1, confirmed=0)에는 잡히지 않고 있습니다. 아래 절차/수치는 당시 기록으로 남겨둡니다.

## 1. 목적

이번 작업은 생체 에너지 전체 피처가 아니라 온도 관련 데이터만 사용해서 정상 baseline 모델을 만든 것이다.

온도 관련 피처만 사용하면 호흡, 거리, 환기, 급수, CO2 같은 비온도 요인이 빠지므로 모델 범위는 좁아진다. 대신 “온도/체온 흐름만 봤을 때 정상과 다른가”를 더 직접적으로 설명할 수 있다.

## 2. 특허에서 참고한 설계 포인트

첨부 특허는 체표 온도를 이용해 아프리카돼지열병 감염 의심축을 추정하는 방법을 다룬다.

참고한 핵심 구조:

- 1단계: 돈방 내 돈군을 열화상 카메라로 관찰한다.
- 2단계: 돈군 중 기준 온도 이상 개체를 선별한다.
- 3단계: 선별 개체의 특정 부위 ROI 온도를 다시 측정한다.
- 4단계: 특정 부위 온도가 기준 이상이면 감염 의심축으로 본다.

참고 기준:

- 돈군 최대 체표 온도 기준: 38도 내지 40도, 바람직하게는 38.5도 내지 39.5도
- 귀 주변부 체표 온도 기준: 36도 내지 38도
- 목 주변부 체표 온도 기준: 38도 내지 40도
- 서혜부 체표 온도 기준: 41도 내지 42도
- 직장 온도 고열 참고: 40.5도 내지 42도

주의:

- 특허의 핵심은 열화상 기반 체표 온도와 ROI 온도다.
- 현재 AI Hub 생체 에너지 데이터에는 열화상 ROI 원본이 없다.
- 따라서 이번 모델은 특허를 그대로 구현한 것이 아니라, 보유 데이터의 온도/체온 피처로 특허의 “온도 중심 2단계 판단” 방향을 참고한 것이다.

## 3. 사용 피처

이번 모델에는 아래 9개 피처만 사용했다.

| 피처 | 의미 |
| --- | --- |
| `T_mean` | 돈사 환경 온도 평균 |
| `rectal_temperature_mean` | 직장 체온 평균 |
| `back_temperature_mean` | 등 체온 평균 |
| `neck_temperature_mean` | 목 체온 평균 |
| `head_temperature_mean` | 머리 체온 평균 |
| `rectal_temperature_std` | 직장 체온 변동성 |
| `back_temperature_std` | 등 체온 변동성 |
| `neck_temperature_std` | 목 체온 변동성 |
| `head_temperature_std` | 머리 체온 변동성 |

제외한 항목:

- 암모니아
- CO2
- 호흡수
- 거리/움직임
- 환기량
- 급이/급수
- 현열/잠열
- 분뇨량
- frame count

현열/잠열은 열량 계열이지만 직접 온도 센서값은 아니므로 이번 온도 전용 모델에서는 제외했다.

## 4. 모델 결과

| 항목 | 값 |
| --- | ---: |
| 원본 집계 row | 650 |
| baseline 사용 row | 624 |
| 제외 row | 26 |
| 학습 window | 308 |
| 검증 window | 65 |
| 입력 피처 수 | 9 |
| sequence length | 24 |

Threshold 비교:

| 기준 | threshold | raw anomaly windows | confirmed anomaly windows |
| --- | ---: | ---: | ---: |
| p95 | 1.566780 | 4 | 0 |
| p97 | 1.594982 | 2 | 0 |
| p99 | 1.766111 | 1 | 0 |

운영용 실험 기준:

- p99 threshold: `1.766111`
- raw anomaly: 1개
- confirmed anomaly: 0개

해석:

- 현재 baseline 안에서는 온도 흐름만 봤을 때 연속 이상 구간이 없다.
- 새 데이터가 들어왔을 때 온도 anomaly score가 p99 기준을 넘고, 연속 3개 window 이상 유지되면 온도 기반 이상 후보로 볼 수 있다.

## 5. 주요 요인

점수가 높은 window에서 복원 오차가 컸던 온도 요인은 다음 순서다.

1. 직장 체온 평균
2. 돈사 온도 평균
3. 머리 체온 평균
4. 머리 체온 변동성
5. 목 체온 평균
6. 등 체온 평균
7. 직장 체온 변동성
8. 등 체온 변동성
9. 목 체온 변동성

즉 현재 온도 전용 모델은 주로 직장 체온, 돈사 온도, 머리/목/등 체온 흐름 차이에 민감하다.

## 6. 산출물

- `artifacts/bioenergy_temperature_baseline/best_model.keras`
- `artifacts/bioenergy_temperature_baseline/final_model.keras`
- `artifacts/bioenergy_temperature_baseline/bioenergy_detection_report.md`
- `artifacts/bioenergy_temperature_baseline/bioenergy_pca_cluster_scatter.jpg`
- `artifacts/bioenergy_temperature_baseline/bioenergy_top_feature_error_bar.jpg`
- `artifacts/bioenergy_temperature_baseline/bioenergy_explanation_report.md`
- `artifacts/bioenergy_temperature_baseline/bioenergy_threshold_comparison.csv`

## 7. 다음 설계 권장

특허 내용을 참고하면 온도 전용 감지는 아래처럼 2단계로 설계하는 것이 좋다.

1. 온도 패턴 모델
   - 현재 만든 LSTM Autoencoder
   - 온도 흐름이 정상 baseline과 다른지 확인

2. 지식 기반 온도 rule
   - 돈군/체표 계열: 38.5도 이상 후보
   - 목 주변부 계열: 38.5도 이상 후보
   - 서혜부 계열: 40.8도 이상 후보
   - 직장 체온: 40.5도 이상 고열 후보

현재 데이터에는 귀/서혜부 체표 ROI가 없으므로, 바로 적용 가능한 rule은 아래가 현실적이다.

- `rectal_temperature_mean >= 40.5`
- `neck_temperature_mean >= 38.5`
- `T_mean`은 돈사 환경 온도이므로 ASF 체표 기준과 직접 혼동하지 않고 별도 환경 고온 기준으로 관리

최종 알림은 다음처럼 분리해서 표시하는 것을 권장한다.

```text
temperature_model_alert = 온도 패턴이 baseline과 다름
temperature_rule_alert = 특허/현장 기준 온도 초과
final_temperature_alert = temperature_model_alert OR temperature_rule_alert
```
