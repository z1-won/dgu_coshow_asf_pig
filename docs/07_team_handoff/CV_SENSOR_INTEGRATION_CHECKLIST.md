# CV-Sensor 통합 체크리스트

## 1. 팀원에게 받을 파일

- [ ] CSV 파일 1개 이상
- [ ] 필수 컬럼: `frame`, `track_id`, `x`, `y`, `w`, `h`, `conf`
- [ ] 권장 컬럼: `source_video`, `pen_id`, `fps`, `frame_width`, `frame_height`, `timestamp`
- [ ] bbox 좌표 기준 확인: 현재 프로젝트는 `x, y = 좌상단` 기준
- [ ] 60프레임 샘플 외에 가능하면 5분 이상 연속 영상 결과 확보

## 2. 파일 배치

권장 위치:

```text
/Users/bangjiwon/dev/pigproject/data/raw/external/cv_tracking/
```

파일명 예시:

```text
pigtrack_pen01_60frames.csv
pigtrack_pen01_5min.csv
```

## 3. 변환 실행

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
pig-cv-tracking-features   --input data/raw/external/cv_tracking/pigtrack_pen01_60frames.csv   --output-dir artifacts/cv_tracking_features
```

## 4. 품질 확인 기준

| 항목 | 기준 | 해석 |
|---|---:|---|
| 평균 confidence | 0.8 이상 | detector 신뢰도 양호 |
| track coverage ratio | 0.8 이상 | ID 유지 양호 |
| low confidence box 비율 | 10% 이하 | 프레임 품질 양호 |
| detected pigs 최소값 | 실제 두수와 큰 차이 없음 | 누락 적음 |
| ID switch 의심 | 낮을수록 좋음 | 별도 육안 확인 필요 |

## 5. 모델 결합 순서

- [ ] 1단계: feature 산출만 확인
- [ ] 2단계: 기존 activity feature와 컬럼 호환성 확인
- [ ] 3단계: 돈방 단위 활동량 지표를 대시보드 상세 근거에 표시
- [ ] 4단계: 이벤트 라벨이 있는 구간에서 recall/false alert 비교
- [ ] 5단계: 충분한 영상 길이가 확보되면 LSTM 입력 feature로 편입

## 6. 현재 주의점

- 60프레임만으로 질병/열스트레스 성능을 주장하지 않는다.
- TIRPigEar 결과는 Lepton 실제 영상 전에는 보조 실험으로 둔다.
- RGB tracking은 바로 feature로 쓸 수 있지만, 개체별 이상탐지까지 가려면 더 긴 영상과 ID 안정성 검증이 필요하다.
