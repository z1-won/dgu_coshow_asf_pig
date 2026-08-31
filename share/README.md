# Team Share Files

이 폴더는 팀원이 GitHub에서 바로 확인할 수 있도록 만든 최소 공유용 산출물이다.
원본 데이터 전체가 아니라, 센서/규칙 파트 결과와 CV YOLO/PigTrack 통합에 필요한 CSV만 포함한다.

## 먼저 볼 파일

`yolo_cctv_focus_input.csv`

센서/규칙 기반으로 먼저 이상 후보로 선별된 돈방과 시간대 목록이다.
CV 파트는 이 파일의 `chamber_id`, `start_datetime`, `end_datetime`을 기준으로 해당 구간 영상을 우선 분석하면 된다.

주요 컬럼:

| 컬럼 | 의미 |
|---|---|
| `chamber_id` | 확인할 돈방 ID |
| `start_datetime`, `end_datetime` | 확인할 시간 구간 |
| `policy_level` | 현재는 `cctv_focus` 중심 |
| `track_score` | 센서/규칙 기반 위험 점수 |
| `management_score` | 급이/사양관리 이상 점수 |
| `environment_score` | 온도/가스 등 환경 이상 점수 |
| `alert_category` | 이상 원인 분류 |
| `reason` | 후보로 잡힌 규칙 근거 |
| `recommended_action` | 권장 확인 행동 |

## 함께 참고할 파일

| 파일 | 용도 |
|---|---|
| `combined_action_queue.csv` | 전체 운영 확인 큐 |
| `management_queue.csv` | 급이/사양관리 관련 후보 |
| `environment_queue.csv` | 온도/CO2/NH3 등 환경 관련 후보 |
| `incident_queue.csv` | 실제 관찰 이벤트와 연결된 후보 |
| `cv_tracking_results_template.csv` | YOLO/PigTrack 결과 CSV 템플릿 |

## CV 파트가 반환할 CSV 형식

필수 컬럼:

```csv
frame,track_id,x,y,w,h,conf
```

권장 컬럼:

```csv
source_video,pen_id,frame,track_id,x,y,w,h,conf,fps,frame_width,frame_height,timestamp
```

주의사항:

- `x`, `y`는 bbox의 좌상단 좌표 기준이다.
- `w`, `h`는 bbox width/height 픽셀 단위다.
- 같은 돼지는 영상 안에서 `track_id`가 최대한 유지되어야 한다.
- `pen_id`는 가능하면 `chamber_id`와 맞춰 기록한다.
- 원본 영상, 모델 가중치, API key, 원본 데이터 ZIP은 이 저장소에 올리지 않는다.

## 변환 명령

팀원이 YOLO/PigTrack 결과 CSV를 만들면 아래 위치에 넣고 변환한다.

```text
data/raw/external/cv_tracking/
```

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
pig-cv-tracking-features \
  --input data/raw/external/cv_tracking/<팀원_YOLO결과파일>.csv \
  --output-dir artifacts/cv_tracking_features
```

생성되는 주요 결과:

```text
artifacts/cv_tracking_features/cv_tracking_motion_rows.csv
artifacts/cv_tracking_features/cv_tracking_track_summary.csv
artifacts/cv_tracking_features/cv_tracking_frame_features.csv
artifacts/cv_tracking_features/cv_tracking_pen_summary.csv
data/processed/cv_tracking_activity_features.csv
```
