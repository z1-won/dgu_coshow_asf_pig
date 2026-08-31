# 팀원 공유용 통합 Handoff

이 문서는 센서/LSTM/규칙 기반 이상탐지 파트와 CV YOLO/PigTrack 파트를 합치기 위한 공유 기준이다.

## 현재 우리 파트의 목적

목표는 ASF 확진 모델이 아니라, 돈방 또는 개체가 정상 패턴에서 벗어나는 시점을 조기 선별하는 운영 모니터링 시스템이다.

현재 파이프라인은 다음 흐름으로 구성되어 있다.

```text
센서/외부 검증 데이터
→ 돈방 또는 개체 단위 시계열 feature
→ LSTM Autoencoder / rule score
→ 돈방 단위 anomaly score
→ 운영 대시보드 / 확인 필요 큐
```

## 현재 보유 데이터와 역할

| 데이터 | 현재 역할 | 팀원 파트와 연결점 |
|---|---|---|
| AI Hub 622 | 카메라 행동량 보조 트랙 | CV tracking feature와 가장 가까운 형식 |
| AI Hub 71408/71763 | 체온·환경 센서 기반 메인 트랙 | CV feature와 결합할 최종 돈방 score 대상 |
| ClearFarm | 실제 농장 급이/환경/건강 관찰 검증 | 환경·급이 rule 검증 근거 |
| HotPig | 고온 스트레스 sanity check | 고온 상태에서 행동/환경 변화 검증 |
| SOWELL | 고온/저온/급이경쟁 등 외부 이벤트 검증 | 환경 이벤트 중 센서 반응 근거 |
| PRRSV/ASFV | 질병 challenge 외부 검증 | 체온/활동량 rule 방향성 검증 |

## 현재 성능/검증 수치 요약

| 항목 | 수치 | 해석 |
|---|---:|---|
| ClearFarm 조기 선별 | recall 73.1%, precision 37.1%, F1 49.2% | 운영자 확인 후보로는 가능, 확정 진단은 아님 |
| ClearFarm 고확신 알림 | precision 46.4%, specificity 83.0%, recall 26.1% | 오탐을 줄이면 놓침이 커짐 |
| Lead-time recall | 24/48/72h 모두 50.0% | 현재 이벤트 수가 적어 신뢰도 제한 |
| ASF 체온 rule | precision 95.0%, sensitivity 48.7%, specificity 99.5% | 체온 단독은 고정밀 보조 rule |
| HotPig | HS anomaly 11.8% vs TN 0.9% | 고온 스트레스 상태에 모델이 반응 |
| SOWELL 고온/저온 | 이벤트 중 탐지율 100.0% | 환경 이벤트 검증 근거로 강함 |

## 센서 파트가 CV 파트로 넘길 파일

ClearFarm scorecard와 3단계 알림 정책을 action queue 스키마로 변환해 두었다. 팀원 YOLO/PigTrack 모델은 아래 파일에서 `cctv_requested=True`인 후보만 먼저 보면 된다.

```text
/Users/bangjiwon/dev/pigproject/artifacts/clearfarm_action_queue/clearfarm_config/yolo_cctv_focus_input.csv
```

핵심 컬럼:

| 컬럼 | 의미 |
|---|---|
| `chamber_id` | 확인해야 할 돈방 ID |
| `start_datetime`, `end_datetime` | 확인 대상 시간 구간 |
| `policy_level` | 현재는 `cctv_focus` 중심 |
| `track_score` | 센서/규칙 기반 위험 점수 |
| `management_score` | 사료 섭취 저하 등 사양관리 점수 |
| `environment_score` | CO2/NH3/고온 등 환경 점수 |
| `alert_category` | `management`, `environment` 등 원인 카테고리 |
| `reason` | 어떤 규칙 때문에 선정됐는지 |
| `recommended_action` | 현장/CCTV 확인 권장 행동 |

즉 CV 파트는 처음부터 전체 영상을 다 분석한다고 주장하지 않고, 센서 파트가 고른 `cctv_focus` 돈방의 행동/자세 근거를 보강하는 역할로 합치면 된다.

## CV 파트에서 주면 바로 받을 수 있는 파일 형식

필수 컬럼은 다음 7개다.

```csv
frame,track_id,x,y,w,h,conf
```

권장 전체 형식은 다음과 같다.

```csv
source_video,pen_id,frame,track_id,x,y,w,h,conf,fps,frame_width,frame_height,timestamp
```

템플릿 파일:

`/Users/bangjiwon/dev/pigproject/data/templates/cv_tracking_results_template.csv`

## 보안/공유 기준

GitHub에는 코드, 설정 예시, 문서, 작은 템플릿만 올린다. 원본 영상, 원본 센서 데이터, 모델 가중치, 실제 API 키는 올리지 않는다.

| 구분 | GitHub 업로드 | 이유 |
|---|---|---|
| 코드/테스트/문서 | 가능 | 협업과 재현에 필요 |
| 템플릿 CSV | 가능 | 실제 농장 정보가 없는 형식 예시 |
| 원본 CCTV 영상 | 금지 | 농장/촬영 시점/시설 정보가 노출될 수 있음 |
| YOLO 모델 가중치(`.pt`, `.pth`, `.onnx`) | 금지 | 용량이 크고 모델 자산이므로 별도 공유 필요 |
| 원본 센서 CSV/ZIP | 금지 | 농장 운영 데이터와 날짜 정보가 포함될 수 있음 |
| `.env`, API key, 토큰 | 금지 | 외부 서비스 접근 권한 노출 위험 |

팀원이 YOLO 결과를 공유할 때는 가능하면 원본 영상 대신 추론 결과 CSV만 전달한다. 발표/대시보드용으로 외부에 보여줄 때는 `pen_id`, `source_video`, 실제 날짜가 특정 농장이나 촬영 파일명으로 연결되지 않도록 익명화한다.

## 우리가 CV 결과로 만들 feature

| 출력 feature | 의미 | 활용 |
|---|---|---|
| `movement_px` | frame 간 중심점 이동거리 | 개체별 활동량 |
| `speed_px_per_sec` | 초당 이동 속도 | 영상 fps가 있을 때 사용 |
| `track_coverage_ratio` | track ID 유지율 | 추적 품질 평가 |
| `low_motion_ratio` | 거의 움직이지 않은 비율 | 저활동/질병 후보 |
| `high_motion_ratio` | 빠르게 움직인 비율 | 과활동/스트레스 후보 |
| `detected_pigs` | frame별 탐지 개체 수 | 누락/가림 품질 관리 |
| `center_movement` | 돈방 전체 이동량 | 기존 activity pipeline 결합 |

## 이미 구현된 변환 명령

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
pig-cv-tracking-features   --input data/templates/cv_tracking_results_template.csv   --output-dir artifacts/cv_tracking_features
```

출력 파일:

| 파일 | 내용 |
|---|---|
| `artifacts/cv_tracking_features/cv_tracking_motion_rows.csv` | bbox별 중심점/이동량 |
| `artifacts/cv_tracking_features/cv_tracking_track_summary.csv` | 개체별 track 유지율/활동량 |
| `artifacts/cv_tracking_features/cv_tracking_frame_features.csv` | frame별 돈방 활동량 |
| `artifacts/cv_tracking_features/cv_tracking_pen_summary.csv` | 돈방별 요약 |
| `data/processed/cv_tracking_activity_features.csv` | 기존 activity pipeline 호환 포맷 |

## 결합 방식

최초 결합은 모델 재학습보다 feature-level 결합으로 시작한다.

```text
PigDetect/PigTrack 결과 CSV
→ cv_tracking_features.py
→ 개체별/돈방별 활동 feature
→ 기존 activity feature와 같은 축으로 정규화
→ LSTM anomaly score 또는 rule score와 결합
→ dashboard에서 카메라 행동분석 근거로 표시
```

## 팀원 결과에 대한 현재 판단 반영

- RGB PigDetect는 1차 detector로 사용 가능하다. 보고된 수치가 P=0.998, R=0.875, mAP50=0.884, mAP50-95=0.815라 실제 농장 영상 기준으로 충분히 좋다.
- PigBench/PigTrack 60프레임 결과는 짧은 구간 track 품질 sanity check로 유효하다. 6마리 중 5마리의 ID가 안정적으로 유지된 점은 활동량 feature 추출에 충분한 출발점이다.
- TIRPigEar는 바로 핵심 지표로 쓰지 않는다. mAP50 약 0.85, mAP50-95 약 0.48이고 자세 변화에 취약하므로 실제 Lepton 영상 확보 후 파인튜닝 대상이다.

## 합치기 전 합의해야 할 최소 사항

1. bbox의 `x, y`가 좌상단 기준인지 중심점 기준인지 확정한다. 현재 우리 템플릿은 좌상단 기준이다.
2. `w, h`는 width/height 픽셀 단위로 통일한다.
3. 같은 영상 안에서 `track_id`가 개체별로 유지되어야 한다.
4. `source_video`, `pen_id`, `fps`, `frame_width`, `frame_height`를 가능하면 반드시 포함한다.
5. 실제 운영 데이터로 성능을 주장하려면 `timestamp` 또는 이벤트 라벨이 필요하다.

## 이번 주 통합 목표

1. 팀원이 PigTrack 결과 60프레임 전체 CSV를 템플릿 형식으로 제공한다.
2. 우리는 `pig-cv-tracking-features`로 개체별/돈방별 활동량 feature를 산출한다.
3. track 품질 지표를 확인한다: 평균 confidence, track 유지율, 누락 frame.
4. 돈방 단위 `center_movement`, `low_motion_ratio`, `high_motion_ratio`를 기존 anomaly feature 후보에 추가한다.
5. 대시보드 상세 근거에 `카메라 행동분석` 근거로 표시한다.
