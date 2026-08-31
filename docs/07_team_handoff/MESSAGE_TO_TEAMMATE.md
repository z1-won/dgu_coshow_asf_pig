# 팀원에게 보낼 메시지 초안

우리 쪽 센서/LSTM/규칙 기반 이상탐지 파트와 CV tracking 파트를 합칠 수 있게 입력 포맷과 변환 코드를 맞춰뒀습니다.

PigTrack/YOLO 결과를 CSV로 받을 수 있으면 바로 결합 가능합니다. 필수 컬럼은 아래 7개입니다.

```csv
frame,track_id,x,y,w,h,conf
```

가능하면 아래 컬럼까지 같이 넣어주세요.

```csv
source_video,pen_id,frame,track_id,x,y,w,h,conf,fps,frame_width,frame_height,timestamp
```

주의할 점은 현재 우리 변환 코드는 `x, y`를 bbox 좌상단 좌표로 가정합니다. 만약 중심점 좌표라면 알려주세요.

우리는 이 CSV에서 개체별 이동량, 속도, track 유지율, 저활동 비율, 돈방 전체 활동량을 뽑아서 기존 이상탐지 feature와 합칠 예정입니다. 60프레임 샘플도 가능하고, 가능하면 5분 이상 연속 영상 결과가 있으면 더 좋습니다.

관련 문서:

- `/Users/bangjiwon/dev/pigproject/docs/07_team_handoff/TEAM_INTEGRATION_HANDOFF.md`
- `/Users/bangjiwon/dev/pigproject/docs/07_team_handoff/CV_SENSOR_INTEGRATION_CHECKLIST.md`
- `/Users/bangjiwon/dev/pigproject/docs/02_modeling/CV_TRACKING_FEATURE_INTEGRATION.md`
- `/Users/bangjiwon/dev/pigproject/data/templates/cv_tracking_results_template.csv`
