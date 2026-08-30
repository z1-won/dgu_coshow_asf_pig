# 다음 작업 계획

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

> **업데이트 (2026-08-26, 돈방별 scaler 적용 후)**: 이 문서의 Step 1~5 수치는 전체 데이터를 scaler 1개로 통합 정규화하던 시점의 기록입니다. 이후 돈방(`dataset_key`+`chamber_number`)마다 scaler를 따로 학습하도록 `bioenergy_pipeline.py`/`bioenergy_baseline.py`를 수정했습니다 — 돈방마다 원래 값 수준이 달라서 하나의 scaler를 쓰면 그 수준 차이가 진짜 이상 패턴보다 더 크게 잡혀 PCA 상에서 돈방별로 갈라져 보이는 문제가 있었습니다.
>
> 돈방별 scaler로 다시 실행한 뒤 가장 큰 변화는: `bioenergy_split_v2`의 p97 기준 confirmed anomaly가 **3개 → 0개**로 바뀌었고, 그 결과 Step 3(clean baseline)에서 "제외한 26개 row"가 이번 재실행에서는 **0개 제외**로 나왔습니다. 즉 예전에 "이상하게 튀는 구간"으로 보고 정상 기준에서 뺐던 71408/chamber 1 구간이, 실은 돈방 간 scaler 수준 차이 때문에 생긴 착시였을 가능성이 높습니다. Step 4, 5의 threshold도 재계산되어 값이 달라졌습니다 (`bioenergy_clean_baseline_no_nh3` p99 `1.442694` → `2.298732`, `bioenergy_temperature_baseline` p99 `1.766111` → `2.718018`; 둘 다 raw anomaly 1개, confirmed 0개는 동일).
>
> 최신 수치는 각 `artifacts/bioenergy_*` 디렉터리의 `bioenergy_detection_report.md`, `bioenergy_threshold_comparison.csv`를 직접 참고하세요. 아래 Step별 서술은 당시 실행 기록으로 남겨둡니다.

## 1. 우선순위 요약

현재는 AI Hub 라벨 다운로드, 정규화, 생체 에너지 LSTM 입력 생성, Autoencoder 학습/탐지 smoke pipeline까지 완료된 상태다.

다음 목표는 모델 결과를 더 신뢰할 수 있게 만드는 것이다.

추가 업데이트: AI Hub 71471 돼지 발정행동 keypoints 라벨도 다운로드/정규화/호환성 비교/전용 행동 baseline 학습까지 완료했다. 71471은 622 행동량 트랙과 feature mapping은 가능하지만, channel별로 `ESTRUS=Y/N`이 분리되어 있고 전용 baseline에서 발정 validation 구간이 정상보다 강하게 이상으로 잡히지 않았다. 따라서 메인 학습 데이터에는 직접 섞지 않고 보조 행동 검증 결과로만 유지한다.

우선순위:

1. validation split 개선: 완료
2. 생체 에너지 모델 재학습: 완료
3. clean normal baseline 모델 구축: 완료
4. NH3 제외 baseline 재학습 및 PCA 축 설명 개선: 완료
5. 온도 전용 baseline 모델 구축: 완료
6. anomaly score 리포트 고도화: 완료
7. 622 행동/키포인트 트랙 분석: 완료
8. 지식 기반 rule layer 추가: 완료
9. 최종 ensemble 경보 설계: 부분 완료
10. 실제 농장 이벤트 데이터 스키마 작성 및 수집 템플릿 준비: 완료

## 2. Step 1: Validation Split 개선

상태: 완료

현재 문제:

- `X_val`이 20개 window로 작다.
- validation window가 주로 `71763` 중심이다.
- `71408`도 검증에 충분히 포함되어야 한다.

해야 할 일:

- `pig-build-bioenergy`의 split 방식을 개선한다.
- 현재는 돈방별 시간순 80:20 분리다.
- 개선안:
  - dataset별, chamber별로 최소 validation window 수를 보장한다.
  - 데이터 수가 적은 그룹은 `seq_len`을 줄이거나 validation 비율을 늘린다.
  - `71408`, `71763` 각각 train/val window 수를 리포트로 출력한다.

완료 기준:

- `71408`, `71763` 둘 다 validation window가 생성된다.
- 전체 validation window가 최소 50개 이상이 된다.
- split summary CSV가 생성된다.

현재 결과:

- `X_train`: `(309, 24, 24)`
- `X_val`: `(71, 24, 24)`
- `71408` validation windows: 26개
- `71763` validation windows: 45개
- `71408 chamber3`은 전체 timestep이 19개라 `seq_len=24` 조건상 제외
- split summary: `artifacts/bioenergy_split_v2/bioenergy_split_summary.csv`

예상 산출물:

- `artifacts/bioenergy/bioenergy_split_summary.csv`
- `artifacts/bioenergy/X_train.npy`
- `artifacts/bioenergy/X_val.npy`

## 3. Step 2: 생체 에너지 모델 재학습

상태: 완료

이전 상태:

- LSTM Autoencoder 30 epoch 설정으로 학습했다.
- EarlyStopping으로 13 epoch에서 종료됐다.
- threshold는 p99 기준 `0.998697`이다.
- raw anomaly 1개, confirmed anomaly 0개다.

해야 할 일:

- split 개선 후 모델을 다시 학습한다.
- `epochs=50` 또는 `epochs=100`까지 열어두되 EarlyStopping으로 자동 중단한다.
- threshold percentile을 비교한다.

비교할 threshold:

- p95
- p97
- p99

완료 기준:

- threshold별 raw/confirmed anomaly 수 비교표 생성
- 최종 기본 threshold 선택

현재 결과:

- 개선 split 산출물 기준 재학습 완료
- `X_train`: `(309, 24, 24)`
- `X_val`: `(71, 24, 24)`
- EarlyStopping으로 24 epoch에서 종료
- p95 threshold `1.454100`: raw anomaly 4개, confirmed anomaly 4개
- p97 threshold `1.475687`: raw anomaly 3개, confirmed anomaly 3개
- p99 threshold `1.540135`: raw anomaly 1개, confirmed anomaly 0개
- 현재 샘플 검증셋에서는 p97을 실험용 기본 threshold로 선택
- p99는 보수적 운영 기준 후보로 유지

주의:

- validation window가 아직 71개로 작다.
- 일부 짧은 chamber는 validation window 확보를 위해 train/validation 입력 구간이 일부 겹친다.
- 현재 threshold는 운영 확정값이 아니라 다음 데이터 추가 전까지의 실험 기준이다.

산출물:

- `artifacts/bioenergy_split_v2/bioenergy_threshold_comparison.csv`
- `artifacts/bioenergy_split_v2/best_model.keras`
- `artifacts/bioenergy_split_v2/final_model.keras`
- `artifacts/bioenergy_split_v2/bioenergy_detection_report.md`
- `artifacts/bioenergy_split_v2/bioenergy_error_distribution.jpg`
- `artifacts/bioenergy_split_v2/bioenergy_detection_windows.csv`

## 4. Step 3: Clean Normal Baseline 모델 구축

상태: 완료

목적:

- 현재 데이터를 대부분 정상으로 간주한다.
- 단, 이전 모델이 강하게 튄다고 본 구간은 정상 기준 학습에서 제외한다.
- 남은 데이터로 앞으로 들어올 새 데이터의 이상 여부를 판단할 baseline 모델을 만든다.

현재 결과:

- 원본 집계 row: 650
- 제외 row: 26
- baseline 사용 row: 624
- 학습 window: 308
- 검증 window: 65
- 입력 피처: 24
- p99 threshold: `1.424001`
- p99 기준 raw anomaly: 1개
- p99 기준 confirmed anomaly: 0개

산출물:

- `artifacts/bioenergy_clean_baseline/best_model.keras`
- `artifacts/bioenergy_clean_baseline/final_model.keras`
- `artifacts/bioenergy_clean_baseline/bioenergy_detection_report.md`
- `artifacts/bioenergy_clean_baseline/bioenergy_error_scatter.jpg`
- `../03_modeling_and_rules/CLEAN_BASELINE_MODEL_REPORT.md`

## 5. Step 4: NH3 제외 baseline 재학습 및 PCA 축 설명 개선

상태: 완료

목적:

- 암모니아 피처 `NH3_mean`을 모델 입력에서 제외한다.
- PCA 군집 산포도의 x축, y축 의미를 그래프와 리포트에 명확히 표시한다.

현재 결과:

- 새 산출물 경로: `artifacts/bioenergy_clean_baseline_no_nh3`
- 입력 피처: 23개
- 제외 피처: `NH3_mean`
- 학습 window: 308
- 검증 window: 65
- p99 threshold: `1.442694`
- p99 raw anomaly: 1개
- p99 confirmed anomaly: 0개

산출물:

- `artifacts/bioenergy_clean_baseline_no_nh3/bioenergy_pca_cluster_scatter.jpg`
- `artifacts/bioenergy_clean_baseline_no_nh3/bioenergy_top_feature_error_bar.jpg`
- `artifacts/bioenergy_clean_baseline_no_nh3/bioenergy_explanation_report.md`
- `../03_modeling_and_rules/DOMAIN_RULE_GUIDANCE.md`

## 6. Step 5: 온도 전용 Baseline 모델 구축

상태: 완료

목적:

- 특허의 체표 온도 기반 감염 의심축 추정 방향을 참고한다.
- 현재 보유 데이터 중 온도/체온 관련 피처만 사용해 별도 baseline 모델을 만든다.

사용 피처:

- `T_mean`
- `rectal_temperature_mean`
- `back_temperature_mean`
- `neck_temperature_mean`
- `head_temperature_mean`
- `rectal_temperature_std`
- `back_temperature_std`
- `neck_temperature_std`
- `head_temperature_std`

현재 결과:

- 산출물 경로: `artifacts/bioenergy_temperature_baseline`
- 입력 피처: 9개
- 학습 window: 308
- 검증 window: 65
- p99 threshold: `1.766111`
- p99 raw anomaly: 1개
- p99 confirmed anomaly: 0개

산출물:

- `artifacts/bioenergy_temperature_baseline/bioenergy_pca_cluster_scatter.jpg`
- `artifacts/bioenergy_temperature_baseline/bioenergy_top_feature_error_bar.jpg`
- `artifacts/bioenergy_temperature_baseline/bioenergy_explanation_report.md`
- `../03_modeling_and_rules/TEMPERATURE_ONLY_BASELINE_REPORT.md`

## 7. Step 6: 탐지 리포트 고도화

현재 리포트:

- reconstruction error histogram
- top anomaly window 표
- dataset/chamber별 error summary

추가할 내용:

- 시간순 anomaly score 그래프
- 돈방별 anomaly score heatmap
- threshold p95/p97/p99 비교 그래프
- top anomaly window의 원본 피처 평균값 표시
- 정상 window 평균과 이상 후보 window 평균 비교

완료 기준:

- 팀원이 리포트만 보고 어느 돈방, 어느 기간, 어떤 피처가 이상했는지 파악 가능

예상 산출물:

- `artifacts/bioenergy/bioenergy_error_timeline.jpg`
- `artifacts/bioenergy/bioenergy_chamber_heatmap.jpg`
- `artifacts/bioenergy/bioenergy_top_window_feature_compare.csv`
- `artifacts/bioenergy/bioenergy_detection_report.md`

## 7-1. AI Hub 71471 행동 보조 트랙

상태: 완료

목적:

- 71471 돼지 keypoints 라벨이 622 행동량 트랙을 보조할 수 있는지 확인한다.
- `ESTRUS`/`INJECTION` 라벨을 입력 feature에서 제외하고, 평가/설명 라벨로만 사용한다.

현재 결과:

- 다운로드 크기: 약 32MB
- annotation rows: 110,960
- 10분 행동 시계열: 9,644 bins
- 622와 매핑 가능한 행동/위치 feature: 17/17
- 전용 행동 baseline:
  - train normal sequences: 3,856
  - validation normal sequences: 46
  - validation estrus sequences: 49
  - 정상 confirmed anomaly: 0/46
  - 발정 confirmed anomaly: 0/49

판단:

- 71471은 행동량 보조 검증 트랙으로는 유지한다.
- channel 1-8이 모두 `ESTRUS=Y`, channel 9-16이 모두 `ESTRUS=N`이라 발정 효과와 카메라/channel 효과가 섞일 수 있다.
- 메인 ASF/돈방 이상탐지 모델에는 직접 섞지 않는다.

산출물:

- `artifacts/aihub_71471_profile/aihub_71471_profile_report.md`
- `artifacts/aihub_71471_timeseries_report.md`
- `artifacts/aihub_71471_compatibility/aihub_71471_622_compatibility_report.md`
- `artifacts/aihub_71471_behavior_baseline/aihub_71471_baseline_report.md`

## 8. Step 7: 622 행동/키포인트 트랙 분석

현재 상태:

- `622`는 센서 JSON이 아니라 CVAT XML 행동/키포인트 라벨이다.
- 정규화 결과:
  - 전체 1,378,937행
  - point 기반 모델 후보 1,086,941행

주요 label:

- `Lying`
- `Standing`
- `Walking`
- `Suckling`
- `Searching`
- `Watercup`
- `Feedbox`

해야 할 일:

- 행동 label 분포 분석
- 돈방별/시간대별 행동 비율 계산
- `Walking`, `Standing`, `Lying` 비율로 활동성 proxy 생성
- point center 이동량 기반 활동량 proxy 생성

완료 기준:

- 돈방별 활동성 CSV 생성
- 행동 비율 리포트 생성
- 생체 에너지 모델과 결합 가능한 시간 단위 activity feature 생성

예상 산출물:

- `data/processed/aihub_622_activity_features.csv`
- `artifacts/aihub_622_activity_feature_report.md`
- `artifacts/aihub_622_behavior_distribution.jpg`

## 9. Step 8: 지식 기반 Rule Layer 추가

목적:

- 온도/체온/호흡/급수/환기 등 사람이 알고 있는 위험 기준을 모델 결과에 보조 판단으로 붙인다.
- 모델 anomaly와 rule anomaly를 분리해서 설명 가능하게 만든다.

예상 산출물:

- `config/domain_rules.json`
- `src/pigproject/domain_rules.py`
- `artifacts/bioenergy_clean_baseline_no_nh3/bioenergy_rule_flags.csv`
- `artifacts/bioenergy_clean_baseline_no_nh3/bioenergy_combined_alert_report.md`

## 10. Step 9: 통합 경보 설계

상태: 부분 완료 (2026-08-28)

구현한 것: `pigproject.final_ensemble`(`pig-final-ensemble`)이 생체 에너지 트랙(`bioenergy_rule_flags.csv`, 모델+규칙 결합 disease_score)과 행동량 트랙(`activity_model_10min`의 pig-detect 결과, `pig-activity-report`로 새로 리포트화)을 같은 점수 척도로 표준화해 `data/processed/final_chamber_anomaly_scores.csv`(window 단위)와 `artifacts/final_chamber_summary.csv`(돈방 단위 요약), `artifacts/final_chamber_alert_report.md`로 만든다.

아직 못 한 것: 아래 설계된 `0.65 * bioenergy + 0.35 * activity` 가중 결합은 **적용되지 않는다**. 71408/71763(2022-11~2023-09)과 622(2021)가 서로 다른 농장·기간의 데이터셋이라 같은 물리적 돈방을 가리키는 chamber가 하나도 없기 때문이다(자세한 내용은 `final_ensemble.py` 모듈 docstring과 `../02_data_preparation/CHAMBER_TIMESERIES_LIMITATION.md` 참고). 같은 돈방에서 두 신호가 동시에 확보되는 실데이터가 들어오면 가중 결합 로직을 켜는 것이 다음 단계.

**정규화 방식 수정 (2026-08-28)**: `activity_model_dataset.py`가 원래 train 전체에 스케일러 1개(`StandardScaler`)만 fit했는데, 이건 생체 에너지 트랙에서 이미 검증하고 고친 것과 같은 문제(`b6c3ec6`)를 그대로 갖고 있었다. 622 데이터셋에서 facility3-pen8의 `active_behavior_ratio` 평균이 `0.615`인데 나머지 8개 pen은 `0.05~0.12`대로, pen 간 절대 수준 차이가 5~10배였다. `fit_scalers_per_pen`/`transform_per_pen`으로 `(facility_number, pen_number)`별 스케일러로 바꾼 뒤 실제로 순위가 뒤집혔다: 이전(전체 통합 스케일러) 기준 mean_error 최상위 pen은 `facility5-pen4`(0.52)였고 `facility3-pen6`은 최하위(0.25)였는데, per-pen 스케일러 적용 후에는 `facility3-pen6`이 raw anomaly가 걸리는 최상위 pen(mean 0.72, max 1.67)으로 뒤집혔다 -- 전체 스케일러가 `facility3-pen6`의 pen 내부 변동을 절대값이 작다는 이유로 완전히 가려버리고 있었다는 뜻이다. p99 threshold는 `0.597672` -> `1.658845`로, 90% bootstrap CI 상대폭은 `2.7%` -> `35.5%`로 커졌다(pen별로 나눠 fit하면서 표본이 더 쪼개졌기 때문 -- 예상된 트레이드오프). `tests/test_activity_model_dataset.py`에 per-pen 스케일링 동작을 고정하는 단위 테스트 추가.

**split 방식 수정 (2026-08-28)**: `activity_model_dataset.split_train_val`이 원래 AI Hub가 제공하는 `split`(training/validation) 컬럼을 그대로 썼는데, 이 공식 split이 9개 facility/pen 조합 중 3개(facility3-pen7: val 9행, facility3-pen8: val 4행, facility5-pen3: val 7행)에 `seq_len=24` window 하나도 못 채울 만큼 적은 validation 행만 배정하고 있었다. 그 결과 이 3개 pen은 threshold 계산에 전혀 반영되지 않은 채 조용히 빠지고 있었다(리포트에 그 사실도 안 드러남). `bioenergy_pipeline.split_by_group_time`을 `group_cols` 파라미터로 일반화해서(`("dataset_key","chamber_number")` -> `("facility_number","pen_number")`) 재사용하도록 바꿨다 -- AI Hub 공식 split 대신, 이미 생체에너지 트랙에서 검증된 "그룹별 시간순 분리 + 최소 val window 보장" 로직으로 전환. `min_val_windows=3`(생체에너지는 10)으로 짧게 잡은 이유는 이 pen들의 전체 기록 자체가 43~56행뿐이라서다.

결과: `X_val` 62 -> 70 windows, 9개 pen 전부 최소 3개 이상의 val window를 갖게 됨(2개는 `overlap_for_short_group`로 train/val이 16~17행 겹침, `activity_split_summary.csv`에 명시). 부작용: 가장 짧은 pen(facility3-pen7, train 7 window뿐)이 reconstruction error가 압도적으로 높게 나와(mean 10.7 vs 나머지 pen 0.3~2.8) threshold가 `1.66` -> `10.98`로 튀었고, bootstrap CI 상대폭이 `35.5%` -> `64.1%`로 커져 `pig-detect`가 자동으로 "통계적으로 불안정" 경고를 띄운다. 이건 버그가 아니라 이전에 조용히 숨겨져 있던 데이터 부족 문제가 (의도대로) 드러난 것 -- 이 pen의 threshold는 지금 신뢰할 수 없다는 걸 정직하게 보여준다.

또한 행동량 트랙에는 아직 도메인 규칙 레이어가 없어(`domain_rules.py`는 생체 에너지 컬럼 전용) `activity_622` track의 disease tier는 model 성분(최대 1.0)만으로 계산되고, 그래서 co-occurrence 보너스가 필요한 "high" tier에는 절대 도달하지 않는다. 이건 의도된 보수적 동작(단일 신호만으로 고위험 판정하지 않음)이지 버그가 아니다.

**전처리 신뢰성 감사 (2026-08-28)**: 위 스케일링/split 수정과 결측치/이상치 점검, facility3-pen7 "참고용" 처리 방침을 `../02_data_preparation/ACTIVITY_PREPROCESSING_AUDIT.md` 하나로 정리했다. 결측치/이상치는 현재 데이터 기준 위험 낮음(NaN 0개, ratio 전부 [0,1] 범위)을 확인했고, `rest_behavior_count`/`rest_behavior_ratio`가 `lying_count`/`lying_ratio`와 완전히 중복된다는 부수적 발견은 기록만 하고 아직 미수정.

최종 목표:

- 생체 에너지 이상점수와 행동/활동성 이상점수를 합쳐 돈방 단위 조기경보를 만든다.

권장 구조:

- Bio-energy anomaly score
  - 체온
  - 호흡수
  - keypoint distance
  - 환경센서
  - 열량/분뇨/사양관리

- Behavior/activity anomaly score
  - 행동 label 비율
  - 이동량 proxy
  - lying/standing/walking 변화

최종 score 예시:

```text
final_score = 0.65 * bioenergy_score + 0.35 * activity_score
```

처음에는 단순 weighted average로 시작하고, 이후 검증 데이터가 늘어나면 weight를 조정한다.

완료 기준:

- 돈방별 최종 anomaly score 생성
- threshold 초과 + 연속 N회 조건 적용
- 최종 경보 CSV 생성

예상 산출물:

- `data/processed/final_chamber_anomaly_scores.csv`
- `artifacts/final_chamber_alert_report.md`

## 10-1. Step 10: 실제 농장 이벤트 데이터 스키마 작성

상태: 완료 (2026-08-29)

목적:

- 모델이 낸 최종 경보를 실제 농장 사건 기록과 맞춰 볼 수 있게 한다.
- 지금의 AI Hub 데이터에는 ASF 확진/의심 이벤트 로그가 없으므로, 운영 성능을 평가하려면 별도 이벤트 표준 양식이 필요하다.
- 이 데이터는 모델 입력 feature가 아니라, 모델 경보의 타당성을 검증하는 평가/운영 기록이다.

구현한 것:

- `pigproject.farm_event_schema`(`pig-farm-events`) 추가
- 실제 농장 이벤트 CSV 템플릿 생성
- 필수 컬럼/schema 검증
- `data/processed/final_chamber_anomaly_scores.csv`의 최종 alert window와 이벤트 시간 겹침 매칭
- 이벤트 시작 전 24/48/72시간 lead-time 사전 경보 평가
- 이벤트 유형별/돈방별 요약 리포트 생성

필수 컬럼:

- `event_id`
- `farm_id`
- `chamber_id`
- `event_type`
- `start_datetime`
- `end_datetime`
- `severity`
- `vet_confirmed`
- `source`
- `notes`

산출물:

- `../05_operations_feedback/FARM_EVENT_DATA_SCHEMA.md`
- `data/templates/farm_event_log_template.csv`
- `data/processed/farm_event_log_clean.csv` (실제 input을 넣었을 때 생성)
- `artifacts/farm_event_schema_issues.csv` (실제 input을 넣었을 때 생성)
- `artifacts/farm_event_alert_matches.csv` (실제 input을 넣었을 때 생성)
- `artifacts/farm_event_lead_time_matches.csv` (실제 input을 넣었을 때 생성)
- `artifacts/farm_event_lead_time_summary.csv` (실제 input을 넣었을 때 생성)
- `artifacts/farm_event_schema_report.md` (실제 input을 넣었을 때 생성)

다음에 필요한 실제 데이터:

- 농장/돈방 ID가 최종 경보의 `chamber_id`와 매핑되어야 한다.
- 사건 시작/종료 시간이 있어야 한다.
- 최소한 `fever`, `respiratory`, `feed_drop`, `water_drop`, `mortality`, `treatment`, `asf_suspected`, `asf_confirmed` 중 하나로 구분되어야 한다.
- `vet_confirmed=true`인 사건이 있어야 precision/recall에 가까운 평가가 가능하다.

## 11. 바로 다음 실행 순서

가장 먼저 할 작업은 실제 농장 이벤트 CSV를 받아 schema 검증을 통과시키고, 최종 경보 window와 매칭해 retrospective evaluation 표를 만드는 것이다.

실행 순서:

1. 농장별 실제 이벤트 로그를 `data/raw/farm_events/farm_event_log.csv` 형식으로 수집
2. `pig-farm-events --input data/raw/farm_events/farm_event_log.csv`로 schema error 확인
3. `chamber_id`가 최종 경보 테이블의 ID와 맞지 않으면 매핑 테이블 추가
4. event_type별 recall, alert 기준 precision proxy, lead time 리포트 확인
5. 실제 이벤트가 들어오면 가상 이벤트(`synthetic-*`)를 제거하고 같은 검증 명령 재실행
6. 결과를 바탕으로 threshold/연속 window 조건 재조정

추가 업데이트: 사양관리/환경 규칙을 먼저 강화했다. `feed_drop`은 기존 유지, `water_drop`, `ventilation_low`, `co2_high`, `nh3_high`, `ventilation_low_with_co2_high`, `ventilation_low_with_nh3_high`를 `config/domain_rules.json`에 추가했고, `domain_rules.py`는 `all_of` 복합 규칙을 지원한다. 낮은 심각도 환경 신호는 `rule_observation`으로 남기되 단독으로는 최종 경보가 되지 않도록 `rule_score >= 0.8`부터 `rule_anomaly`로 승격한다.

현재 데이터 재계산 결과:

- bioenergy rule anomaly: 20 -> 26
- final ensemble alert window: 20 -> 26
- 새로 늘어난 6개는 `co2_high + nh3_high` 조합이다.
- `feed_drop`, `water_drop`, `ventilation_low`는 현재 validation window에서는 직접 hit가 없다. 즉 규칙은 준비됐지만, 실제 개선 효과는 관련 사건/센서 패턴이 들어오는 데이터에서 확인해야 한다.

규칙 추가 전/후 비교 리포트도 생성했다:

- `pigproject.rule_upgrade_compare`(`pig-compare-rule-upgrade`) 추가
- `artifacts/rule_upgrade_compare_report.md`
- `artifacts/rule_upgrade_compare_summary.csv`
- `artifacts/rule_upgrade_reason_compare.csv`
- `artifacts/rule_upgrade_new_alerts.csv`
- `artifacts/rule_upgrade_lead_time_compare.csv`

비교 결과:

- baseline rules: final alert 20, high tier 0, medium tier 20
- upgraded rules: final alert 26, high tier 10, medium tier 16
- `rectal_temp_high` 20개 중 10개가 `rectal_temp_high + co2_high`로 승격되어 high tier가 됐다.
- 새 final alert 6개는 `co2_high + nh3_high` 환경 조합이다.
- synthetic event 기준 lead-time recall은 24h 16.7%, 48h 16.7%, 72h 33.3%로 유지됐다. 새 alert가 실제/가상 이벤트와 72시간 lead-time 안에 연결되지는 않았기 때문이다.

규칙 검증용 synthetic 이벤트도 분리했다:

- `pigproject.synthetic_rule_events`(`pig-build-synthetic-rule-events`) 추가
- `pigproject.synthetic_rule_evaluation`(`pig-evaluate-synthetic-rule-events`) 추가
- `data/raw/farm_events/synthetic_rule_positive_events.csv`
- `data/raw/farm_events/synthetic_rule_negative_events.csv`
- `data/raw/farm_events/synthetic_mixed_events.csv`
- `artifacts/synthetic_rule_injection_checks.csv`
- `artifacts/synthetic_rule_evaluation_report.md`

검증 결과:

- positive set: 24/48/72h recall 모두 100%
- negative set: 24/48/72h recall 모두 0%
- mixed set: 24/48/72h recall 모두 50%
- `rectal_temp_high`, `rectal_temp_high+co2_high`, `co2_high+nh3_high`는 실제 hit window 기반 positive 이벤트에서 정상적으로 잡힌다.
- `feed_drop`, `water_drop`, `ventilation_low`는 현재 validation window 실제 hit가 없다.
- injection 검증에서는 `feed_drop`, `water_drop`, `ventilation_low` 모두 rule_fired는 True다. Risk category 분리 후 단독 `feed_drop`/`water_drop`은 `management_alert=True`로 올라가며, `ventilation_low` 단독은 낮은 환경 관찰 신호로만 남는다.

Risk category 분리도 반영했다:

- `config/domain_rules.json`의 각 rule에 `category` 추가
- `domain_rules.py`에서 `disease_rule_score`, `management_rule_score`, `environment_rule_score` 계산
- `bioenergy_rule_flags.csv`에 `disease_alert`, `management_alert`, `environment_alert`, `alert_category` 추가
- `final_chamber_anomaly_scores.csv`에 `management_score`, `environment_score`, `operational_alert` 추가
- 해석 문서: `../05_operations_feedback/RISK_CATEGORY_ALERTS.md`

최신 결과:

- disease alert: 20
- management alert: 0
- environment alert: 6
- final alert: 26
- 새로 늘어난 6개는 질병이 아니라 `co2_high + nh3_high` 환경 경보이다.

Category별 lead-time 평가도 추가했다:

- `pigproject.category_lead_time_report`(`pig-category-lead-time`) 추가
- `artifacts/category_lead_time_metrics.csv`
- `artifacts/category_lead_time_events.csv`
- `artifacts/category_lead_time_report.md`

`synthetic_mixed_events.csv` 기준 결과:

- final/operational recall: 24/48/72h 모두 50%
- disease recall: 24/48/72h 모두 33.3%
- environment recall: 24/48/72h 모두 16.7%
- management recall: 0% (`feed_drop`, `water_drop` 실제 alert window가 현재 데이터에 없기 때문)

이제 전체 recall 하나만 보지 않고, 질병/사양관리/환경 대응 queue별로 따로 평가할 수 있다.

Management synthetic scenario도 final ensemble까지 연결했다:

- `pigproject.synthetic_management_scenario`(`pig-build-synthetic-management-scenario`) 추가
- `artifacts/synthetic_management_scenario/bioenergy_rule_flags.csv`
- `data/raw/farm_events/synthetic_management_events.csv`
- `data/processed/synthetic_management_final_chamber_anomaly_scores.csv`
- `artifacts/synthetic_management_final_chamber_alert_report.md`
- `artifacts/synthetic_management_category_lead_time_report.md`

검증 결과:

- synthetic management final alert: 28 / 131
- management alert window: 2
- synthetic feed_drop/water_drop 이벤트 2개 모두 management category에서 24/48/72h recall 100%
- disease category recall은 0%로 유지된다. 즉 사양관리 이상을 질병 경보로 과장하지 않고 management queue로만 올리는 흐름이 확인됐다.

Category action queue도 추가했다:

- `pigproject.action_queue_report`(`pig-action-queues`) 추가
- 기본 최종 경보 기준 산출물:
  - `artifacts/action_queues/combined_action_queue.csv`
  - `artifacts/action_queues/disease_queue.csv`
  - `artifacts/action_queues/management_queue.csv`
  - `artifacts/action_queues/environment_queue.csv`
  - `artifacts/action_queues/action_queue_report.md`
- synthetic management 기준 산출물:
  - `artifacts/synthetic_management_action_queues/combined_action_queue.csv`
  - `artifacts/synthetic_management_action_queues/disease_queue.csv`
  - `artifacts/synthetic_management_action_queues/management_queue.csv`
  - `artifacts/synthetic_management_action_queues/environment_queue.csv`
  - `artifacts/synthetic_management_action_queues/action_queue_report.md`

현재 기본 데이터 기준 action item:

- disease queue: 20
- management queue: 0
- environment queue: 6

synthetic management scenario 기준 action item:

- disease queue: 20
- management queue: 2
- environment queue: 6

이제 경보를 단순 score 목록이 아니라 `수의학 확인`, `급이/급수 점검`, `환기/가스 점검` 업무 큐로 분리해서 볼 수 있다.

Incident review log도 추가했다:

- `pigproject.incident_review`(`pig-build-incident-review-log`) 추가
- 기본 incident review 산출물:
  - `data/processed/incident_review_log.csv` (2026-08-30: 1회성 템플릿에서 누적 로그로 전환 -- 재실행해도 기존 리뷰 상태 유지, `--dashboard-export`로 대시보드 확인/오탐 결과 병합 가능)
  - `data/processed/incident_review_summary_history.csv` (실행마다 스냅샷 추가, 리뷰율/precision 추이 확인용)
  - `artifacts/incident_review_summary.csv`
  - `artifacts/incident_review_report.md`
- synthetic management incident review 산출물:
  - `data/templates/synthetic_management_incident_review_log_template.csv`
  - `artifacts/synthetic_management_incident_review_summary.csv`
  - `artifacts/synthetic_management_incident_review_report.md`

리뷰 로그에는 `review_status`, `confirmed`, `false_alarm`, `actual_cause`, `resolved_at`, `operator_note`, `reviewed_by`, `reviewed_at`, `followup_required`, `followup_action`을 기록한다. 이 값이 채워지면 category별 precision 추정과 오탐 원인 분석에 바로 쓸 수 있다.

Rule tuning recommendation도 추가했다:

- `pigproject.rule_tuning_recommendation`(`pig-rule-tuning-recommendations`) 추가
- 산출물:
  - `artifacts/rule_tuning_recommendations.csv`
  - `artifacts/rule_tuning_recommendations_report.md`
  - `artifacts/synthetic_management_rule_tuning_recommendations.csv`
  - `artifacts/synthetic_management_rule_tuning_recommendations_report.md`
- 현재 실제 리뷰 로그는 전부 pending이므로 threshold 조정은 보류된다. 현재 리포트 기준 `전체 rule 11개`, `리뷰 근거 rule 0개`, `추가 리뷰 필요 11개` 상태다.
- 리뷰가 3건 이상 쌓이면 rule별로 `tighten_threshold`, `keep_or_relax_carefully`, `improve_data_capture`, `monitor` 후보를 자동으로 낸다.

Sample review scenario도 추가했다:

- `pigproject.sample_review_scenario`(`pig-build-sample-review-scenario`) 추가
- 산출물:
  - `data/templates/sample_incident_review_log.csv`
  - `artifacts/sample_incident_review_summary.csv`
  - `artifacts/sample_incident_review_report.md`
  - `artifacts/sample_rule_tuning_recommendations.csv`
  - `artifacts/sample_rule_tuning_recommendations_report.md`
- 기본 incident 3건 기준 샘플 결과:
  - reviewed: 3 / 3
  - confirmed: 2
  - false_alarm: 1
  - 전체 precision estimate: 66.7%
  - disease precision estimate: 100%
  - environment precision estimate: 0%
- 다만 rule별 threshold 조정은 rule당 리뷰 3건 이상부터 권고하므로, 현재 샘플에서는 `collect_more_reviews`가 유지된다.

Rule threshold experiment도 추가했다:

- `pigproject.rule_threshold_experiment`(`pig-rule-threshold-experiment`) 추가
- 산출물:
  - `artifacts/rule_threshold_experiment_summary.csv`
  - `artifacts/rule_threshold_experiment_reason_compare.csv`
  - `artifacts/rule_threshold_experiment_report.md`
- 현재 후보 실험 결과:
  - baseline final alert: 26, disease alert: 20, environment alert: 6
  - `co2_high=1100`: final alert 20, disease alert 20, environment alert 0
  - `co2_high=1200`: final alert 20, disease alert 20, environment alert 0
  - `nh3_high=12`: final alert 20, disease alert 20, environment alert 0
  - 모든 후보가 disease alert 손실 없이 environment alert 6개를 제거한다.
- 가장 보수적인 1차 후보는 `co2_high=1100`이다. 다만 실제 적용은 environment incident가 오탐으로 3건 이상 확인된 뒤 하는 것이 맞다.

Candidate rule config도 추가했다:

- `pigproject.rule_candidate_config`(`pig-build-rule-candidate-config`) 추가
- `pigproject.rule_config_compare`(`pig-compare-rule-configs`) 추가
- 산출물:
  - `config/domain_rules_candidate_co2_1100.json`
  - `artifacts/rule_candidate_config_changes.csv`
  - `artifacts/rule_candidate_config_report.md`
  - `artifacts/rule_candidate_config_compare_summary.csv`
  - `artifacts/rule_candidate_config_compare_reason.csv`
  - `artifacts/rule_candidate_config_compare_report.md`
- baseline config 대비 candidate config 결과:
  - final alert: 26 -> 20
  - disease alert: 20 -> 20
  - management alert: 0 -> 0
  - environment alert: 6 -> 0
- 결론: 후보 config는 질병 경보를 줄이지 않고 환경 단독 경보만 제거한다. 실제 운영 반영은 review log에서 environment false_alarm 근거가 더 쌓인 뒤 진행한다.

## 8. 현재 기준 명령

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
```

생체 에너지 배열 생성:

```bash
pig-build-bioenergy \
  --input data/processed/aihub_71408_features.csv \
  --input data/processed/aihub_71763_features.csv \
  --output-dir artifacts/bioenergy \
  --seq-len 24 \
  --min-val-windows 10
```

학습:

```bash
pig-train --artifact-dir artifacts/bioenergy --epochs 30 --batch-size 16
```

탐지:

```bash
pig-detect --artifact-dir artifacts/bioenergy --percentile 99 --consecutive-required 3
```

리포트:

```bash
pig-bioenergy-report --artifact-dir artifacts/bioenergy --seq-len 24
```

## 9. 팀원 분담 제안

역할 A: 데이터 파이프라인

- split 개선
- feature aggregation 확인
- 결측/중복 처리 정책 정리

역할 B: 모델링

- LSTM Autoencoder 구조 실험
- threshold percentile 비교
- 연속 경보 조건 실험

역할 C: 행동 트랙

- 622 XML 행동 label 분석
- 활동성 proxy 설계
- 행동 시각화 생성

역할 D: 발표/보고서

- 프로젝트 배경 정리
- 파이프라인 도식화
- 결과 시각화 정리
- ASF 조기 선별이라는 한계와 의의 명확화
