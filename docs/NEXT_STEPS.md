# 다음 작업 계획

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 1. 우선순위 요약

현재는 AI Hub 라벨 다운로드, 정규화, 생체 에너지 LSTM 입력 생성, Autoencoder 학습/탐지 smoke pipeline까지 완료된 상태다.

다음 목표는 모델 결과를 더 신뢰할 수 있게 만드는 것이다.

우선순위:

1. validation split 개선: 완료
2. 생체 에너지 모델 재학습: 완료
3. clean normal baseline 모델 구축: 완료
4. NH3 제외 baseline 재학습 및 PCA 축 설명 개선: 완료
5. 온도 전용 baseline 모델 구축: 완료
6. anomaly score 리포트 고도화
7. 622 행동/키포인트 트랙 분석
8. 지식 기반 rule layer 추가
9. 최종 ensemble 경보 설계

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
- `docs/CLEAN_BASELINE_MODEL_REPORT.md`

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
- `docs/DOMAIN_RULE_GUIDANCE.md`

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
- `docs/TEMPERATURE_ONLY_BASELINE_REPORT.md`

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

## 11. 바로 다음 실행 순서

가장 먼저 할 작업은 Step 7 지식 기반 rule layer 추가다.

실행 순서:

1. 시간순 anomaly score 그래프 생성
2. 돈방별 anomaly score heatmap 생성
3. threshold p95/p97/p99 비교 그래프 생성
4. top anomaly window의 원본 피처 평균값 산출
5. 정상 window 평균과 이상 후보 window 평균 비교
6. `bioenergy_detection_report.md`에 결과 통합

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
