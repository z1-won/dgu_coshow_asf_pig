# HotPig 외부 데이터 기반 탐지 sanity check

작성일: 2026-08-26
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`
데이터 출처: [HotPig (Zenodo 17090997)](https://zenodo.org/records/17090997) -- 개체별 사육 돼지 24마리, 정상(TN)/고온스트레스(HS) 대조 실험, CC-BY-4.0

## 1. 왜 필요했나

지금까지 AI Hub 생체 에너지 데이터(71408/71763)로 만든 모델은 confirmed anomaly가 계속 0개였다. 이게 "탐지기가 정말 이상을 못 잡는 것"인지 "애초에 이 데이터에 진짜 이상이 없어서"인지 구분할 방법이 없었다 -- AI Hub 데이터는 전부 "정상으로 가정"한 데이터라 진짜 이상 사례(ground truth)가 없기 때문이다.

HotPig은 이 문제를 정확히 풀어준다: 24마리를 열중성(TN, 22도, 7일) -> 고온스트레스(HS, 32도, 7일)로 통제 실험한 데이터라 **진짜 "정상"과 "이상 확인됨"이 둘 다 있다.**

## 2. 방법

- `series.zip`(분당 행동빈도 + 사료섭취, 개체별 23,040분/16일)을 받아 10분 단위로 리샘플링
- 개체(pig_id)를 `bioenergy_pipeline.py`의 돈방-scaler 메커니즘에서 쓰는 "chamber"로 취급 -- HotPig은 개체당 측정 밀도가 충분해서 (`../02_data_preparation/CHAMBER_TIMESERIES_LIMITATION.md`에서 AI Hub 데이터가 불가능했던 것과 달리) 개체별 스케일링이 실제로 의미가 있다
- TN 구간만으로 학습(train 18,626 / val 4,254 윈도우, seq_len=24 = 4시간), 같은 LSTM Autoencoder 구조로 학습
- 한 번도 학습에 쓰지 않은 HS 구간(23,640윈도우)에 대해 TN-val 기준으로 잡은 threshold(p99)를 그대로 적용해서 탐지

모듈: `src/pigproject/hotpig_sanity_check.py`, CLI `pig-hotpig-sanity-check`.
평가 모듈: `src/pigproject/hotpig_evaluate.py`, CLI `pig-hotpig-evaluate`.

## 3. 결과

| 구간 | window 수 | raw anomaly | 비율 |
| --- | ---: | ---: | ---: |
| TN validation (정상, 학습에 안 쓴 held-out) | 4,254 | 40 | 0.94% |
| HS test (고온스트레스, 학습에 전혀 안 쓴 구간) | 23,640 | 2,796 | 11.83% |

**정상 대비 약 12.6배 높은 탐지율.** threshold는 TN validation만으로 잡았고 HS 구간은 완전히 미학습 상태였다. 다만 이번 재현에서 threshold p99의 bootstrap CI 상대폭이 56%라, 운영 threshold로 고정하기보다는 외부 sanity check 방향성 근거로 해석해야 한다.

### 시간 경과에 따른 탐지율 (HS 1일차 ~ 7일차)

| HS 경과일 | 탐지율 |
| --- | ---: |
| 1일차 | 16.3% |
| 2일차 | 14.1% |
| 3일차 | 11.3% |
| 4일차 | 11.1% |
| 5일차 | 10.4% |
| 6일차 | 8.8% |
| 7일차 | 10.5% |

**고온스트레스 초기(1~2일차)에 가장 민감하게 반응하고, 이후 점차 낮아진다.** 이는 급성 스트레스 반응 이후 개체가 부분적으로 적응하는 축산 생리학 패턴과 일치한다 -- 우연한 잡음이라면 이런 일관된 시간 추세가 나오지 않는다.

## 4. 해석과 한계

- **이건 우리 파이프라인(LSTM Autoencoder + per-individual scaler + percentile threshold)이 실제 물리적 이상 상태에 반응한다는 첫 외부 검증 근거다.** 지금까지 AI Hub 데이터만으로는 확인 못 했던 부분이다.
- 단, HotPig은 ASF가 아니라 열스트레스 실험이고, 개체/사육방식/국가가 다르다. "이 방법론이 진짜 이상 상태에 반응할 수 있다"는 근거이지, "우리 AI Hub 기반 모델이 ASF를 잡는다"는 증명은 아니다.
- 탐지율이 11.8%로 100%가 아니라는 것도 정직하게 봐야 한다 -- 모든 HS window가 "이상"으로 보이는 건 아니고, 스트레스여도 행동 패턴이 정상 범주에 머무는 시간대가 더 많다는 뜻이다.

## 5. 발표에 쓸 수 있는 한 줄

> "AI Hub 데이터에는 확인된 이상 사례가 없어서, 정상/이상이 실험적으로 통제된 외부 공개 데이터셋(HotPig)으로 우리 탐지 파이프라인을 검증했다. 학습에 전혀 쓰지 않은 고온스트레스 구간에서 정상 대비 약 12.6배 높은 탐지율을 보였고, 스트레스 초기에 더 민감하게 반응하는 것까지 확인했다."
