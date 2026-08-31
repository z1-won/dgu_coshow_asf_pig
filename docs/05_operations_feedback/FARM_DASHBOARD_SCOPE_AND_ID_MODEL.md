# 농장 단일 스코프와 돈방 비교 모델

## 전제

운영 대시보드는 여러 농장을 비교하는 화면이 아니다. 로그인한 한 농장의 돈사와 돈방만 표시하는 단일 농장 스코프 화면이다.

현재 데모 데이터는 AI Hub `71408`, `71763`, `622` 등 서로 다른 공개 데이터셋에서 온 산출물을 사용한다. 따라서 이 값들을 실제 같은 농장/같은 기간의 원천 데이터라고 해석하면 안 된다. 대시보드에서는 발표용으로 `demo-farm` 아래의 `1동`, `2동`, `3동`처럼 매핑해 보여주되, 모델 검증 문서에서는 원 데이터 출처를 계속 유지한다.

## 운영 ID 계층

| 계층 | 필드 | 의미 |
| --- | --- | --- |
| 농장 | `farm_id` | 로그인한 농장 단위. 운영 화면은 이 범위 밖의 데이터는 보여주지 않는다. |
| 돈사/동 | `building_id` | 같은 농장 안의 물리적 동. 돈방 비교의 1차 기준이다. |
| 돈방 | `pen_id` / `chamber_id` | 실제 모니터링되는 공간 단위. 이상탐지의 기본 단위다. |
| 카메라 | `camera_id` | 돈방 또는 돈방 묶음을 관찰하는 CCTV 장비 ID다. |
| 센서 | `sensor_id` | 체온, 급이, 급수, CO2, NH3, 온습도, 환기 등 설비/센서 ID다. |

## 화면 비교 기준

메인 돈방 배치도는 농장 간 비교가 아니라 같은 `building_id` 안의 돈방끼리 비교한다.

- `max_score_rank`: 같은 동 안에서 이상 점수가 몇 번째로 높은지
- `compared_pens`: 비교 대상 돈방 수
- `delta_from_barn_mean`: 같은 동 평균 이상 점수 대비 차이

예시: `1동 1/4 · 평균 대비 +0.73`

이 값은 운영자가 “이 돈방이 자기 농장 안에서 얼마나 튀는지”를 빠르게 판단하기 위한 정보다.

## 현재 구현

- 정적 대시보드 스냅샷: `dashboard/scripts/generate-dashboard-data.mjs`
- API 변환: `src/pigproject/dashboard_data.py`
- 화면 표시: `dashboard/src/App.jsx`, `dashboard/src/components/Header.jsx`

## 다음 확장

실제 농장 데이터가 들어오면 공개 데이터셋 ID를 직접 노출하지 않고 아래 매핑 파일을 추가한다.

```csv
farm_id,building_id,pen_id,chamber_id,camera_id,sensor_group_id
farm-a,barn-1,pen-01,bioenergy:71408:1,CAM-01,ENV-01
farm-a,barn-1,pen-02,bioenergy:71408:2,CAM-01,ENV-01
```

이 매핑이 들어오면 팀원 YOLO/ByteTrack 결과도 `camera_id`, `pen_id`, `timestamp` 기준으로 같은 돈방에 연결할 수 있다.
