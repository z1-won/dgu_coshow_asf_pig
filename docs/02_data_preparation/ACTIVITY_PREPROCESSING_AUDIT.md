# 행동량(622) 트랙 전처리 신뢰성 감사

작성일: 2026-08-28
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 1. 배경

생체 에너지 트랙(71408/71763)은 챔버별 스케일러, min-val-windows 보장 split, 부트스트랩 threshold 신뢰구간, 실제 ASF 데이터 검증까지 거친 뒤였는데, 행동량 트랙(622)은 같은 검증을 거치지 않은 채 `artifacts/activity_model_10min`에 LSTM Autoencoder 결과만 올라가 있었다. 이 문서는 "통상적인 데이터 전처리 신뢰성 체크리스트"(스케일링 일관성 → 결측/이상치 처리 → split 검증 → 문서화) 순으로 행동량 트랙을 점검하고 고친 내역을 정리한다.

## 2. 스케일링 일관성 (수정 완료)

**발견**: `activity_model_dataset.fit_transform()`이 train 전체에 `StandardScaler` 하나만 fit하고 있었다. 622 데이터셋에서 facility3-pen8의 `active_behavior_ratio` 평균은 `0.615`인데 나머지 8개 pen은 `0.05~0.12`대 — pen 간 절대 수준 차이가 5~10배였다. 이건 생체에너지 트랙에서 이미 검증하고 고친 문제(챔버별 baseline 차이가 통합 스케일러 하에서 진짜 이상치보다 크게 잡힘, `b6c3ec6`)와 동일한 패턴이다.

**수정**: `bioenergy_pipeline.fit_scalers_per_chamber`/`transform_per_chamber`와 동일한 방식으로 `fit_scalers_per_pen`/`transform_per_pen`을 추가해 `(facility_number, pen_number)`별 스케일러로 전환.

**효과(before/after 실측)**:
- 이전(통합 스케일러): mean reconstruction error 최상위 pen = facility5-pen4(0.52), facility3-pen6은 최하위(0.25)
- 이후(pen별 스케일러): **순위가 뒤집힘** — facility3-pen6이 raw anomaly가 걸리는 최상위(mean 0.72, max 1.67)로 올라오고 facility5-pen4는 3위로 밀림
- facility3-pen6이 절대값 자체가 작아 통합 스케일러 하에서는 그 pen 내부의 변동이 완전히 가려져 있었다는 뜻. threshold도 `0.598 → 1.659`로, 90% bootstrap CI 상대폭이 `2.7% → 35.5%`로 커짐(pen별로 fit하면서 표본이 쪼개진 예상된 트레이드오프).

## 3. Split 검증 -- min-val-windows 보장 (수정 완료)

**발견**: 622 데이터셋에는 AI Hub가 제공하는 `split`(training/validation) 컬럼이 있고, 원래 코드는 이 컬럼을 그대로 썼다. 그런데 9개 facility/pen 조합 중 3개는 이 공식 split이 `seq_len=24` window 하나도 못 채울 만큼 적은 validation 행만 배정하고 있었다(facility3-pen7: val 9행, facility3-pen8: val 4행, facility5-pen3: val 7행). 이 3개 pen은 threshold 계산에 전혀 반영되지 않은 채 리포트에도 안 드러나고 조용히 빠지고 있었다.

**수정**: `bioenergy_pipeline.split_by_group_time`을 `group_cols` 파라미터로 일반화해 재사용 -- AI Hub 공식 split 대신 이미 생체에너지 트랙에서 검증된 "그룹별 시간순 분리 + 최소 val window 보장" 로직으로 전환(`min_val_windows=3`, 생체에너지는 10; 이 pen들의 전체 기록 자체가 43~56행뿐이라 짧게 잡음).

이 리팩터 과정에서 재사용한 `overlap_rows` 계산이 `338`, `303` 같은 값을 내는 버그를 추가로 발견했다: `load_timeseries`가 정렬 1순위로 `"split"` 컬럼을 쓰고 있어서 같은 pen의 행들이 인덱스상 두 블록(전체 training 블록 / 전체 validation 블록)으로 흩어져 있었기 때문. 정렬 키에서 `split`을 빼고 `facility_number, pen_number, datetime` 순으로 바꿔서 해결(수정 후 정상 범위인 16, 17로 나옴).

**효과**: `X_val` 62 → 70 windows, 9개 pen 전부 최소 3개 이상 검증됨(2개는 `overlap_for_short_group`로 train/val이 16~17행 겹침, `activity_split_summary.csv`에 명시).

## 4. 결측치/이상치 감사 (점검 완료, 위험 낮음 확인 + 투명성 보강)

**점검 결과** (`data/processed/aihub_622_activity_timeseries_10min.csv`, 1,126행 기준):
- 모델 입력 29개 feature 전부 **NaN 0개**.
- 모든 `*_ratio` feature가 `[0, 1]` 범위 안에 있음 -- 생체에너지 트랙의 `rectal_temperature_mean`처럼 물리적으로 말이 안 되는 값(32.3도 같은 센서 노이즈)이 나올 위험이 구조적으로 낮음(카운트 비율이라 범위가 자연히 bounded).
- 음수 값 없음.

**발견한 부수적 이슈(수정하지 않음, 참고용)**: `rest_behavior_count`/`rest_behavior_ratio`가 `lying_count`/`lying_ratio`와 **완전히 동일**하다(상관계수 1.0). 622 데이터셋에는 `Resting`/`Sitting` 라벨이 아예 등장하지 않아서(`REST_LABELS = {Lying, Resting, Sitting}`) 사실상 중복 feature 2개가 모델에 들어가고 있다. 수치적으로 위험하진 않지만(모델이 못 돌아가거나 하지 않음), reconstruction error에서 "lying" 신호가 사실상 2배 가중되는 효과가 있을 수 있다. `DEFAULT_FEATURE_COLUMNS`에서 `rest_behavior_count`/`rest_behavior_ratio`를 빼는 건 간단하지만 모델 입력 shape(29→27)이 바뀌므로 이번 감사에서는 고치지 않고 기록만 남긴다.

**투명성 보강(수정 완료)**: `load_timeseries()`가 결측/비수치 값을 그룹별 보간(interpolate) 후 `fillna(0)`으로 조용히 채우고 있었는데, 이건 생체에너지 트랙의 `filter_implausible_values`가 "무엇을 얼마나 걸러냈는지 항상 리포트한다"는 원칙과 어긋났다. `missing_or_non_numeric` / `filled_by_interpolation` / `zero_filled` 세 지표를 feature별로 계산해 `activity_data_quality_report.csv`로 저장하고 `activity_model_dataset_report.md`에도 요약을 넣도록 수정. 현재 데이터 기준으로는 세 지표 모두 0(위 점검 결과와 일치)이라 지금 당장 동작이 바뀌진 않지만, 앞으로 결측치가 있는 데이터가 들어오면 조용히 사라지지 않고 보고된다.

## 5. 참고용(데이터 부족) pen 처리 방침

min-val-windows 보장 split의 부작용으로, 가장 짧은 pen(facility3-pen7, 전체 56행, train window 7개뿐)의 reconstruction error가 나머지 pen(mean 0.3~2.8)보다 압도적으로 높게(mean ~11) 나와 전체 threshold를 밀어올렸다.

**결정(2026-08-28, 사용자 확인)**: facility3-pen7은 **삭제하지 않고 참고용으로 표시**한다.

**구현**: `activity_model_dataset.LOW_TRAIN_WINDOWS_THRESHOLD = 10`(생체에너지 트랙 자체의 min_val_windows 기본값을 그대로 가져온 기준) 미만의 train window를 가진 pen은 `activity_split_summary.csv`에 `low_confidence=True`로 표시된다. 이 플래그는 아래 산출물까지 전파된다.

- `lstm_detection_report.md`: "참고용(데이터 부족) pen의 window" 섹션으로 분리, headline 수치에 "그중 참고용 pen: N" 병기.
- `final_chamber_alert_report.md`: Chamber별 상위 10 랭킹에서 제외하고 "참고용(데이터 부족) chamber" 섹션에 따로 표시(수치는 삭제하지 않고 `final_chamber_anomaly_scores.csv`/`final_chamber_summary.csv`에 그대로 남음).

현재 이 기준에 걸리는 pen은 facility3-pen7 하나뿐이다(facility3-pen8=13, facility5-pen3=11 train window로 임계값 10을 겨우 넘겨 걸리지 않음).

## 6. 남은 한계

- `rest_behavior_count`/`rest_behavior_ratio` 중복 feature는 기록만 하고 미수정(§4).
- 행동량 트랙에는 아직 도메인 규칙 레이어가 없어(생체에너지만 `domain_rules.py` 보유) disease tier가 model 성분만으로 계산되고, "high" tier(규칙 co-occurrence 필요)에는 도달하지 않는다 -- 의도된 보수적 동작.
- facility3-pen7처럼 train window가 threshold 부근(10개 안팎)인 pen은 앞으로 데이터가 더 들어오면 재평가해야 한다 -- `LOW_TRAIN_WINDOWS_THRESHOLD`는 고정 임계값이라 pen이 자라면 자동으로 플래그가 풀린다.
