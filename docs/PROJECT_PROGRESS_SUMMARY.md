# 돈사 이상탐지 프로젝트 진행 요약

작성일: 2026-08-26  
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

> **업데이트 (2026-08-26, 돈방별 scaler 적용 후)**: 이 문서에 기록된 threshold/anomaly 수치는 전체 데이터를 scaler 1개로 통합 정규화하던 시점의 결과입니다. 이후 돈방별로 scaler를 따로 학습하도록 수정해서 수치가 바뀌었습니다. 자세한 변경 내용과 최신 수치는 [docs/NEXT_STEPS.md](NEXT_STEPS.md) 상단 업데이트 노트와 각 `artifacts/bioenergy_*` 디렉터리를 참고하세요.

## 1. 프로젝트 목표

돈방 단위 돼지 활동량, 호흡, 체온, 환경센서, 생체 에너지 데이터를 활용해 정상 패턴에서 벗어나는 이상 신호를 조기 탐지하는 파이프라인을 구축했다.

현재 목표는 ASF 확진 모델이 아니라, 돈방 단위 조기 선별용 이상탐지 시스템이다.

## 2. 구축한 프로젝트 구조

Python 패키지 형태로 프로젝트를 새로 구성했다.

주요 CLI:

- `pig-aihub`: AI Hub 공식 `aihubshell` 래퍼
- `pig-normalize`: AI Hub 라벨 데이터를 공통 CSV로 정규화
- `pig-validate-data`: 정규화 데이터 품질검증 보고서 생성
- `pig-analyze-sample`: 샘플데이터 분석, 돼지 위치 맵 JPG, 특징 보고서 생성
- `pig-build-bioenergy`: 양돈 생체 에너지 데이터를 LSTM 입력 배열로 변환
- `pig-train`: LSTM Autoencoder 학습
- `pig-detect`: reconstruction error 기반 이상탐지
- `pig-bioenergy-report`: 생체 에너지 탐지 결과 리포트와 오차 분포 JPG 생성

## 3. 샘플데이터 분석

사용한 샘플 경로:

`/Users/bangjiwon/Downloads/Sample`

샘플 구성:

- 라벨 JSON: 200개
- 이미지 PNG: 200개
- 호흡량 데이터: 120개
- 증발량 데이터: 80개
- 돈방: chamber 1~4, 각 50개

생성 산출물:

- `/Users/bangjiwon/dev/pigproject/artifacts/sample_analysis/sample_features.csv`
- `/Users/bangjiwon/dev/pigproject/artifacts/sample_analysis/sample_feature_report.md`
- `/Users/bangjiwon/dev/pigproject/artifacts/sample_analysis/pig_map.jpg`

샘플 분석 결론:

- 호흡량 데이터에는 `distance`, `breath-rate`, 체온 4종이 있어 모델 입력에 적합하다.
- 증발량 데이터에는 `evaporation`, bbox, 열량/분뇨량이 있어 보조 분석 피처로 적합하다.
- 샘플의 `timestamp`는 절대시각이 아니라 프레임 번호 성격이므로, 실제 학습에서는 `date + time + frame_number` 또는 API 측정 시각을 기준으로 정렬해야 한다.

## 4. AI Hub 연동

AI Hub 공식 `aihubshell`을 프로젝트 로컬에 설치했다.

경로:

`/Users/bangjiwon/dev/pigproject/bin/aihubshell`

API 키는 코드에 저장하지 않고 터미널 환경변수로만 사용한다.

```bash
export AIHUB_API_KEY="실제_API_키"
```

확인한 데이터셋:

- `622`: 지능형 스마트축사 통합 데이터(양돈)
- `71408`: 양돈 생체 에너지 데이터
- `71763`: 양돈 생체 에너지 데이터 (2023)

데이터셋 매니페스트:

`/Users/bangjiwon/dev/pigproject/config/aihub_datasets.json`

병렬 데이터 트랙 문서:

`/Users/bangjiwon/dev/pigproject/docs/PARALLEL_DATA_TRACKS.md`

## 5. 다운로드 완료 데이터

원천 이미지는 수십~수백 GB 단위라 받지 않고, 우선 라벨/메타 데이터만 다운로드했다.

다운로드된 원본 경로:

`/Users/bangjiwon/dev/pigproject/data/raw/aihub`

다운로드 결과:

- `622`: 약 15MB, zip 2개
- `71408`: 약 293MB, zip 2개
- `71763`: 약 302MB, zip 3개

## 6. 정규화 결과

각 데이터셋을 공통 CSV 형태로 정규화했다.

정규화 CSV:

- `/Users/bangjiwon/dev/pigproject/data/processed/aihub_622_features.csv`
- `/Users/bangjiwon/dev/pigproject/data/processed/aihub_71408_features.csv`
- `/Users/bangjiwon/dev/pigproject/data/processed/aihub_71763_features.csv`

행 수:

- `622`: 1,378,937행
- `71408`: 365,379행
- `71763`: 360,024행

모델 입력 후보 CSV:

- `/Users/bangjiwon/dev/pigproject/data/processed/aihub_622_model_features.csv`
- `/Users/bangjiwon/dev/pigproject/data/processed/aihub_71408_model_features.csv`
- `/Users/bangjiwon/dev/pigproject/data/processed/aihub_71763_model_features.csv`

모델 후보 행 수:

- `622`: 1,086,941행
- `71408`: 275,188행
- `71763`: 270,011행

데이터셋별 특징:

- `622`는 JSON 센서 데이터가 아니라 CVAT XML 행동/키포인트 라벨이다. 센서 기반 LSTM 입력보다는 행동/활동량 보조 트랙으로 적합하다.
- `71408`, `71763`은 환경센서, 호흡수, keypoint 거리, 체온, 사양관리, 열량 데이터가 포함되어 LSTM 입력에 적합하다.

품질검증 리포트:

- `/Users/bangjiwon/dev/pigproject/artifacts/aihub_622_validation_report.md`
- `/Users/bangjiwon/dev/pigproject/artifacts/aihub_71408_validation_report.md`
- `/Users/bangjiwon/dev/pigproject/artifacts/aihub_71763_validation_report.md`

## 7. 생체 에너지 LSTM 입력 생성

`71408 + 71763` 데이터를 합쳐 LSTM Autoencoder 입력 배열을 만들었다.

처리 방식:

- `dataset_key + chamber_number + datetime` 단위로 집계
- 같은 시각에 여러 프레임이 있는 구조이므로 프레임 원본을 그대로 넣지 않고 집계값을 사용
- 평균 피처와 일부 표준편차 피처를 함께 사용

생성 피처 수:

- 24개

주요 피처:

- `T_mean`, `RH_mean`, `CO2_mean`, `NH3_mean`
- `breath_rate_mean`, `distance_mean`
- `weight_mean`
- 체온 4종 평균
- 사양관리 3종 평균
- `pig_manure_mean`
- `sensible_heat_mean`, `latent_heat_mean`
- `distance_std`, `breath_rate_std`, 체온 표준편차
- `frame_count`

생성 산출물:

- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/bioenergy_aggregated.csv`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/bioenergy_feature_columns.csv`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/X_train.npy`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/X_val.npy`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/bioenergy_scaler.joblib`

배열 크기:

- `X_train`: `(341, 24, 24)`
- `X_val`: `(20, 24, 24)`

## 8. LSTM Autoencoder 학습 및 탐지

모델:

- LSTM Autoencoder
- 입력 shape: `(24, 24)`
- 총 파라미터: 약 69,912개
- 정상 패턴 복원 오차 기반 이상탐지

학습:

- 30 epoch 설정
- EarlyStopping으로 13 epoch에서 종료

생성 모델:

- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/best_model.keras`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/final_model.keras`

탐지 결과:

- threshold: `0.998697`
- raw anomaly windows: 1
- confirmed anomaly windows: 0

연속 3개 window 이상 threshold 초과 시 최종 경보로 판단하도록 구성되어 있다. 현재는 단발 이상 후보만 있고 최종 경보는 없다.

## 9. 탐지 리포트

생성 산출물:

- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/bioenergy_detection_report.md`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/bioenergy_detection_windows.csv`
- `/Users/bangjiwon/dev/pigproject/artifacts/bioenergy/bioenergy_error_distribution.jpg`

최고 오차 window:

- dataset: `71763`
- chamber: `3`
- 기간: `2023-09-07 14:23:00` ~ `2023-09-15 17:34:00`
- reconstruction error: `1.006791`
- raw anomaly: true
- confirmed anomaly: false

## 10. 검증 상태

현재 테스트 상태:

- `pytest`: 2개 테스트 통과

실행 확인 완료:

- 샘플 분석
- AI Hub 목록/filekey 조회
- AI Hub 라벨 다운로드 확인
- 데이터 정규화
- 데이터 품질검증
- 생체 에너지 LSTM 입력 생성
- LSTM 학습
- threshold 산정
- 이상탐지 리포트 생성

## 11. 현재 한계

- `X_val` window가 20개로 아직 작다.
- validation window가 주로 `71763` 중심이다.
- `71408`도 충분히 validation에 포함되도록 split 방식을 개선해야 한다.
- `622`는 센서 시계열이 아니라 행동/키포인트 XML이므로 생체 에너지 모델과 직접 병합하기보다 별도 활동량/행동 트랙으로 다루는 것이 좋다.
- 아직 실제 장기 원천 이미지는 다운로드하지 않았다.

## 12. 다음 작업 제안

1. `71408`, `71763` split 전략 개선
   - 데이터셋별, 돈방별 validation window가 충분히 생기도록 조정

2. 생체 에너지 모델 재학습
   - split 개선 후 30~100 epoch 학습
   - threshold를 p95, p97, p99로 비교

3. 622 행동/키포인트 트랙 분석
   - 행동 label 분포 분석
   - 돈방별 활동량 proxy 생성
   - 시간대별 `Lying`, `Standing`, `Walking` 비율 계산

4. 통합 모델 설계
   - 생체 에너지 모델: 체온, 호흡, 환경센서, 열량 기반
   - 622 행동 모델: 행동/활동량 기반
   - 최종 경보는 두 모델 점수를 ensemble하는 방향

5. 발표/보고서용 시각화
   - reconstruction error trend
   - 돈방별 anomaly score heatmap
   - 피처별 정상 범위 요약

## 13. 재현 명령

가상환경 활성화:

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
```

생체 에너지 입력 배열 생성:

```bash
pig-build-bioenergy \
  --input data/processed/aihub_71408_features.csv \
  --input data/processed/aihub_71763_features.csv \
  --output-dir artifacts/bioenergy \
  --seq-len 24
```

학습:

```bash
pig-train --artifact-dir artifacts/bioenergy --epochs 30 --batch-size 16
```

탐지:

```bash
pig-detect --artifact-dir artifacts/bioenergy --percentile 99 --consecutive-required 3
```

리포트 생성:

```bash
pig-bioenergy-report --artifact-dir artifacts/bioenergy --seq-len 24
```
