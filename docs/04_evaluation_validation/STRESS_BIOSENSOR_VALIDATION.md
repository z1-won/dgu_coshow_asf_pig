# Wearable Stress Biosensor 외부 데이터 기반 탐지 sanity check

작성일: 2026-08-30
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`
데이터 출처: MDPI 논문 Supplementary Files (Suresh et al.) -- 웨어러블 바이오센서 부착 돼지 5마리, 격리(Isolation)/짝사육(Pair) 대조 실험, 1초 단위 심박수/호흡수/체온/자세/가속도/ECG

## 1. 왜 필요했나

기존 외부 검증(HOTPIG, ASF Dryad, Behavior x Heat Tolerance)은 각각 열스트레스, ASF 챌린지, 근육온도 데이터였다. 심박수·호흡수·자세를 실측한 웨어러블 신호로 검증한 적은 없었다 -- AI Hub 생체 에너지 데이터의 "호흡량", "체온"은 영상/센서 기반 추정치이지 심박수 같은 직접 생체신호가 아니다.

이 데이터는 **사회적 격리라는, 지금까지와 다른 종류의 스트레스**로 같은 파이프라인(정상 구간으로 학습한 LSTM Autoencoder + percentile threshold)이 반응하는지 확인할 수 있는 세 번째 외부 sanity check다.

## 2. 방법

- `Supplementary File S1.csv`(1초 단위, 5마리, 318,714행)를 정규화 -- `SkinTemp`/`GSR`은 원본 전체가 센서 sentinel 값(-3276.8, 65535)이라 제외하고, 나머지 채널은 sentinel 값만 개별 마스킹
- `condition`(Isolation/Pair)은 원 논문 코드(`categorize_activity`, `S3_Q1.ipynb`)와 동일한 규칙(`raw_activity_label`에 "pair" 포함 여부)으로 정의 -- 원본 라벨이 단순 이분류가 아니라서 논문 저자의 방법론을 그대로 재현
- 10분 단위로 리샘플링(mean 14개 + 심박수/호흡수/HRV/RR-interval의 std 4개 = 18 feature)
- **`Pair`(정상 사육)만으로 학습, `Isolation`(격리)을 held-out 검증** -- HOTPIG의 TN/HS와 같은 논리
- 녹화가 한 달에 걸친 11번의 짧은 세션(연속 스트림이 아님)이라 bioenergy 기본값 `seq_len=24`(4시간)로는 일부 돼지의 validation window가 0개가 됨 -> `seq_len=12`(2시간), `train_ratio=0.7`로 조정해 4마리 전부 train/val window 확보
- `pig11`은 원본에 Pair 구간이 없어(between-subject) Behavior x Heat Tolerance와 같은 이유로 pooled(전체 통합) scaler 사용

모듈: `src/pigproject/wearable_stress_biosensor_normalize.py`(`pig-normalize-stress-biosensor`), `src/pigproject/wearable_stress_biosensor_dataset.py`(`pig-build-stress-biosensor-dataset`)
평가 모듈: `src/pigproject/wearable_stress_biosensor_evaluate.py`(`pig-evaluate-stress-biosensor`)

## 3. 결과

| 구간 | window 수 | mean error | raw anomaly | confirmed anomaly |
| --- | ---: | ---: | ---: | ---: |
| Pair validation (정상, 학습에 안 쓴 held-out) | 58 | 0.998 | 1.7% | **0.0%** |
| Isolation test (격리 스트레스, 학습에 전혀 안 쓴 구간) | 184 | 1.405 | 40.8% | **39.7%** |

threshold(p99)는 Pair validation만으로 잡았고, bootstrap CI 상대폭은 5.1%로 HOTPIG(56%)보다 훨씬 안정적인 점추정이다.

### 돼지별 confirmed anomaly rate

| pig_id | Pair validation | Isolation test |
| --- | ---: | ---: |
| pig11 | (Pair 구간 없음) | 0%* |
| pig13 | 0% | 42% |
| pig15 | 0% | 24% |
| pig21 | 0% | 52% |
| pig22 | 0% | 44% |

\* pig11은 Isolation window가 2개뿐이라 `consecutive_required=3`(같은 돼지 안에서 3연속) 조건상 raw anomaly rate 50%와 무관하게 confirmed는 항상 0이 된다 -- 표본 부족이지 모델이 반응하지 않은 게 아니다.

## 4. 해석과 한계

- **Pair validation에서 오탐 0%를 유지하면서 Isolation에서만 confirmed anomaly가 39.7%로 뛴다.** 정상으로 학습한 모델이 사회적 격리라는 별개의 스트레스 유형에도 일관되게 반응한다는 두 번째(HOTPIG에 이은) 물리적 스트레스 외부 검증이다.
- 이 데이터는 ASF가 아니라 격리 스트레스 실험이고, 종/개체수(5마리)/센서 종류가 AI Hub 데이터와 다르다. "이 방법론이 실제 생리적 스트레스 신호(심박/호흡/자세)에 반응할 수 있다"는 근거이지, "우리 AI Hub 기반 모델이 ASF를 잡는다"는 증명은 아니다.
- `pig11`은 Pair 기준선이 아예 없는 between-subject 사례라 pooled scaler로만 채점했고, window 수도 2개뿐이라 이 개체만으로는 결론을 내릴 수 없다.
- 표본이 5마리로 적다 -- HOTPIG(24마리)보다 개체 수가 훨씬 적으므로, 방향성 근거로는 유효하지만 통계적 일반화 근거로 과장하지 않는다.

## 5. 발표에 쓸 수 있는 한 줄

> "체온/영상 기반 신호 외에, 심박수·호흡수·자세를 직접 측정한 웨어러블 바이오센서 데이터로도 같은 탐지 파이프라인을 검증했다. 정상 사육 구간에서는 오탐 0%를 유지하면서, 학습에 전혀 쓰지 않은 격리 스트레스 구간에서는 39.7%를 이상으로 확인했다."
