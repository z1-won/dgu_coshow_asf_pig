# CV Tracking Feature Integration

팀원 PigTrack/YOLO 결과가 아직 CSV 파일로 없을 때를 대비해 표준 입력 포맷과 변환 명령을 먼저 고정한다.

## 입력 템플릿

`/Users/bangjiwon/dev/pigproject/data/templates/cv_tracking_results_template.csv`

필수 컬럼:

| column | meaning |
|---|---|
| `frame` | 영상 frame 번호 |
| `track_id` | tracker가 부여한 돼지 ID |
| `x`, `y`, `w`, `h` | bbox 좌상단 좌표와 크기(px) |
| `conf` | detector confidence |

권장 컬럼:

| column | why |
|---|---|
| `source_video` | 여러 영상 구분 |
| `pen_id` | 돈방/pen 연결 |
| `fps` | px/frame을 px/sec로 변환 |
| `frame_width`, `frame_height` | 이동량 정규화 |
| `timestamp` | 실제 운영 시계열과 결합 |

## 변환 명령

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
pig-cv-tracking-features   --input data/templates/cv_tracking_results_template.csv   --output-dir artifacts/cv_tracking_features
```

## 출력

- `artifacts/cv_tracking_features/cv_tracking_motion_rows.csv`: bbox별 중심점/이동량
- `artifacts/cv_tracking_features/cv_tracking_track_summary.csv`: 개체별 track 유지율/활동량
- `artifacts/cv_tracking_features/cv_tracking_frame_features.csv`: frame별 돈방 활동량
- `artifacts/cv_tracking_features/cv_tracking_pen_summary.csv`: 돈방별 요약
- `data/processed/cv_tracking_activity_features.csv`: 기존 activity pipeline 호환 포맷

## 프로젝트 반영 판단

이 feature는 현재 LSTM/규칙 모델의 행동 입력을 보강하기 위한 것이다. 60프레임 테스트는 추적 품질 sanity check로는 충분하지만, 질병/열스트레스 성능 수치로 주장하려면 실제 이벤트 라벨과 더 긴 영상이 필요하다.
