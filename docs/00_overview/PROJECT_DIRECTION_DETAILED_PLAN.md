# 프로젝트 방향 안내 및 세부 계획

작성일: 2026-08-30  
기준 기획: `/Users/bangjiwon/dev/pigproject/지원_베어메모`

## 1. 최초 기획 기준 요약

최초 기획의 핵심 흐름은 다음이다.

```text
농장 데이터 수집
-> 두수/출하/환경 보정
-> 돈방별 정상 패턴 학습
-> Anomaly Score
-> 이상 돈방 선정
-> CCTV 집중 분석
-> 이상 개체 특정
-> Disease/ASF Risk Score
-> 관리자 알림
```

따라서 현재 프로젝트는 처음부터 개별 돼지 진단 모델을 만드는 것이 아니라, 먼저 돈방 단위로 이상 후보를 줄이고 그 다음 CCTV/YOLO 기반 개체 탐지로 내려가는 구조가 맞다.

최초 기획에서 중요하게 잡은 입력 변수는 사료, 음수, CCTV, 돈사 온도/환경 보정이다. 현재 구현은 이 중 체온/환경/활동/호흡 기반 돈방 이상탐지와 규칙 기반 경보까지 진행되어 있고, 사료/음수와 CCTV 개체 localization은 다음 단계에서 강화해야 한다.

## 2. 이번 방향성에 맞춘 프로젝트 목표

### 2.1 시간 범위

사용자 방향에 따라 우선 분석 기간은 ASF 발생률이 높은 1-5월, 즉 상반기 중심으로 둔다.

현재 데이터 산출물에는 11-12월, 8-9월 등 여러 기간이 섞여 있다. 따라서 다음 작업에서는 모델 구조를 바꾸기 전에 먼저 데이터 필터링 기준을 정해야 한다.

우선순위는 다음이다.

1. 1-5월 데이터가 현재 원천 데이터 안에 충분히 있는지 확인
2. 있으면 상반기 전용 split/evaluation 생성
3. 부족하면 현재 데이터로는 계절 우선순위만 설계하고, 추가 데이터 확보를 별도 과제로 둠
4. 이후 하반기 데이터는 비교군으로 사용

### 2.2 탐지 단위

1차 단위는 돈방 하나다. 이유는 최초 기획에서도 돈방 이상도 -> CCTV 집중 분석 -> 이상 개체 특정 순서였고, 현재 AI Hub 71408/71763도 돈방/챔버 단위 시계열에 더 잘 맞기 때문이다.

2차 단위는 개별 돼지다. 단, 개별 돼지 탐지는 현재 LSTM 오토인코더가 직접 담당하는 영역이 아니라 팀원의 CV YOLO 기반 자세 detect 모델이 담당하는 영역으로 분리한다.

정리하면 다음과 같다.

| 단계 | 단위 | 담당 모델/로직 | 산출물 |
| --- | --- | --- | --- |
| 1차 | 돈방 | LSTM Autoencoder + domain rules | 이상 돈방 후보, disease/management/environment queue |
| 2차 | 돈방 내 개체 | YOLO 자세/개체 detect + tracking | 누워있음, 서있음, 음수/급이 접근, 움직임 저하, 이상 개체 후보 |
| 3차 | 운영 판단 | 대시보드 + 관리자 확인 | 알림, 확인 로그, rule/model tuning |

## 3. 현재 성능과 신뢰도 해석

현재 성능은 실제 ASF 확진 라벨 기반 최종 성능이 아니라, 다음 네 가지 기준으로 나눠서 봐야 한다.

### 3.1 LSTM Autoencoder 단독

대표 산출물: `artifacts/bioenergy_clean_baseline/bioenergy_detection_report.md`

- 평가 window: 61개
- threshold: 2.063897
- raw anomaly: 1개
- confirmed anomaly: 0개
- reconstruction error 평균: 1.178117
- p95: 1.903557
- p99: 2.063897

해석: LSTM 단독은 현재 매우 보수적으로 작동한다. 그래서 recall이 낮게 보일 수 있다. 이 모델은 질병을 직접 맞히는 분류기가 아니라, 평소와 다른 패턴을 찾는 baseline detector로 두는 것이 맞다.

### 3.2 최종 돈방 경보

대표 산출물: `artifacts/final_chamber_alert_report.md`

- 전체 window: 131개
- bioenergy window: 61개
- activity_622 window: 70개
- 최종 경보 window: 26개
- disease alert: 20개
- management alert: 0개
- environment alert: 6개

해석: 지금 프로젝트에서 실제로 쓸 수 있는 경보는 LSTM 단독보다 `LSTM + domain rule + category queue` 조합이다. disease는 체온 기반 규칙이 강하게 잡고 있고, management는 실제 사료/음수 이벤트 데이터가 부족해 아직 약하다.

### 3.3 외부 검증

대표 산출물: `artifacts/external_validation_summary/external_validation_summary.md`

- HOTPIG: HS confirmed anomaly rate 11.8% vs TN validation 0.9%, 약 12.6배
- ASF Dryad: `rectal_temp_high=39.5C` 기준 sensitivity 48.7%, specificity 99.5%, precision 95.0%
- Behavior x Heat Tolerance: behavior_only 2.9%, behavior_muscle/full 100.0%

해석: 온도/생리 기반 이상에는 반응한다는 근거가 있다. 다만 ASF 확진 모델이라고 주장하기에는 부족하고, 조기 이상 선별 및 고정밀 규칙 보조로 표현해야 한다.

### 3.4 Lead-Time / 운영 평가

대표 산출물: `artifacts/category_lead_time_report.md`

- synthetic event 6개 기준 final recall_24h/48h/72h: 0.5 / 0.5 / 0.5
- disease recall_24h/48h/72h: 0.333 / 0.333 / 0.333
- environment recall_24h/48h/72h: 0.167 / 0.167 / 0.167
- 평균 first lead time: 23.07시간

해석: 지금 recall은 낮다. 특히 feed_drop, water_drop, treatment 쪽 이벤트는 현재 기본 데이터에서 충분히 잡히지 않는다. 그래서 사양관리 데이터 추가 없이 규칙만으로 일부 개선은 가능하지만, 실제 성능 확정을 위해서는 사료/음수/처치/출하 이벤트 로그가 필요하다.

## 4. LSTM Autoencoder와 YOLO 자세 detect/대시보드 결합 방식

현재 LSTM 오토인코더와 팀원의 YOLO 모델은 경쟁 관계가 아니라 서로 다른 층을 맡는다.

```text
센서/시계열 데이터
-> LSTM Autoencoder
-> 돈방 이상도 계산

체온/사료/음수/환경 기준
-> Domain Rules
-> disease/management/environment 분류

CCTV 영상
-> YOLO 자세 detect + tracking
-> 돈방 내 행동 비율/개체 후보 계산

세 결과 통합
-> 대시보드에서 돈방 우선순위 표시
-> 이상 돈방 클릭 시 개체/자세 근거 표시
```

대시보드에서는 다음처럼 보여주는 것이 좋다.

| 화면 | 보여줄 내용 |
| --- | --- |
| 전체 돈방 지도 | 돈방별 risk tier, 최근 score, category 색상 |
| 돈방 상세 | LSTM anomaly score, rule reason, 체온/환경/사료/음수 추세 |
| CCTV 상세 | YOLO 자세 비율, 활동량 저하, 특정 개체 후보, frame evidence |
| 관리자 확인 | 실제 문제 여부, 원인, 조치, 오탐 여부 입력 |

중요한 설계 원칙은 LSTM이 “어느 돈방을 먼저 볼지”를 정하고, YOLO가 “그 돈방 안에서 어떤 돼지가 이상한지”를 좁히는 것이다.

## 5. 최초 기획 달성률

정량 달성률은 기능 단위로 나눠 보는 것이 적절하다.

| 최초 기획 항목 | 현재 상태 | 달성률 |
| --- | --- | --- |
| 돈방별 정상 패턴 학습 | LSTM Autoencoder 구현 및 산출물 생성 | 80% |
| Anomaly Score 생성 | reconstruction error, track score 생성 | 80% |
| 질병 의심도 계산 | disease score, rectal temp rule, ASF Dryad 검증 | 65% |
| 사료/음수 이상 반영 | rule 틀은 있으나 실제 이벤트/센서 데이터 부족 | 35% |
| 환경 보정 | CO2/NH3/온도 rule 및 후보 threshold 실험 | 60% |
| 이상 돈방 선정 | final chamber alert, action queue 구현 | 75% |
| CCTV 집중 분석 | 622/71471 행동 보조 분석은 있으나 팀 YOLO 결과 연동 전 | 35% |
| 이상 개체 특정 | 아직 통합 전 | 15% |
| 관리자 알림/대시보드 | action queue/review log는 있으나 UI 연동 전 | 40% |
| 리뷰 기반 개선 | incident review, tuning recommendation 구현 | 60% |

전체적으로 보면 최초 1차 목표인 “비육돈 돈방에서 평소와 다른 이상징후를 조기에 감지하고, 관리자가 확인해야 할 돈방을 알려줌”은 약 65-70% 수준까지 왔다.

반면 최종 목표인 “ASF를 AI로 진단”은 아직 25-35% 수준으로 보는 것이 안전하다. 현재 결과는 ASF 확진이 아니라 ASF 의심 신호를 포함한 돈방 이상 조기 선별이다.

> **업데이트 (2026-08-30, ClearFarm 비육돈 실제 농장 검증 이후)**: 위 표의 "질병 의심도 계산"(65%), "사료/음수 이상 반영"(35%), "환경 보정"(60%)은 전부 AI Hub 데이터 기준 수치다. 이번에 처음으로 실제 비육돈 농장(ClearFarm) 건강관찰 라벨로 검증한 결과, `feed_drop`/`co2_high`/`nh3_high`/`barn_temp_high` 4개 규칙 모두 설정된 절대값 threshold가 그대로는 작동하지 않는다는 걸 확인했다(상시발동 또는 전혀 미발동). 즉 위 %는 "AI Hub 안에서 규칙이 그럴듯하게 설계됐다"는 뜻이지 "다른 농장에서도 작동한다"는 뜻이 아니었다는 게 이번에 드러났다 -- 퍼센트를 낮추기보다는, 이 격차 자체를 발표에서 정직하게 설명하고 [FARM_RELATIVE_THRESHOLD_DESIGN.md](../03_modeling_and_rules/FARM_RELATIVE_THRESHOLD_DESIGN.md)의 "농장별 상대 threshold" 다음 단계로 연결하는 게 맞다고 판단했다. 동시에 ClearFarm 건강관찰로 재캘리브레이션하면(`barn_temp_high` precision 47.5%) 규칙 방향성 자체는 유효하다는 것도 확인했다 -- 설계가 아니라 "절대값 하나 공유"라는 구현 방식의 문제라는 근거다. 상세: [CLEARFARM_RULE_VALIDATION_REPORT.md](../04_evaluation_validation/CLEARFARM_RULE_VALIDATION_REPORT.md).

## 6. 앞으로의 세부 실행 계획

### 1순위: 상반기 데이터 가용성 점검

목표: 현재 원천/가공 데이터에서 1-5월 window가 얼마나 있는지 확인한다.

작업:

1. `bioenergy_aggregated.csv`, `final_chamber_summary.csv`, action queue 파일의 날짜 분포 확인
2. 월별 window 수, 돈방 수, 경보 수 집계
3. 1-5월 데이터만으로 학습/검증 가능한지 판단
4. 부족하면 추가 데이터 확보 목록을 갱신

완료 기준:

- `artifacts/seasonal_data_availability_report.md` 생성
- 월별 window 수와 경보 수 표 생성
- 1-5월 우선 분석 가능/불가능 판정

### 2순위: 돈방 하나 기준 MVP 고정

목표: 대시보드/YOLO 연동 전에 대표 돈방 하나를 기준으로 end-to-end 흐름을 완성한다.

작업:

1. 대표 돈방 선정: 경보가 있는 `bioenergy:71408:4` 또는 `bioenergy:71408:2`
2. 정상 구간과 이상 구간 비교
3. LSTM score, rule reason, category queue, lead-time을 한 장 리포트로 묶음
4. 팀원 YOLO 결과가 들어올 수 있는 입력 스키마 정의

완료 기준:

- `artifacts/single_chamber_mvp_report.md` 생성
- 한 돈방 기준 설명 가능한 스토리 완성

### 3순위: 성능 지표판 정리

목표: 지금 결과/신뢰도를 숫자로 한 곳에서 확인한다.

작업:

1. LSTM 단독 지표
2. rule 기반 경보 지표
3. final ensemble 지표
4. external validation 지표
5. lead-time 지표
6. incident review precision proxy

완료 기준:

- `artifacts/performance_scorecard.md` 생성
- 발표/보고서에 넣을 수 있는 핵심 수치 1페이지 정리

### 4순위: YOLO-CV 결합 스키마 정의

목표: 팀원의 CV 모델 결과를 현재 파이프라인에 붙일 수 있게 한다.

필요 입력 컬럼 예시:

| 컬럼 | 의미 |
| --- | --- |
| `farm_id` | 농장 ID |
| `chamber_id` | 돈방 ID |
| `pig_track_id` | 개별 돼지 추적 ID |
| `timestamp` | 프레임 또는 집계 시각 |
| `pose_label` | lying, standing, sitting, feeding, drinking 등 |
| `bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2` | 탐지 위치 |
| `confidence` | YOLO confidence |
| `camera_id` | CCTV ID |

완료 기준:

- `data/templates/yolo_pose_output_schema.csv` 생성
- `docs/02_data_preparation/YOLO_INTEGRATION_SCHEMA.md` 작성

### 5순위: 대시보드 결합 설계

목표: 모델 산출물이 대시보드에서 바로 보이도록 API/파일 단위를 정한다.

작업:

1. 돈방별 summary API 또는 CSV 정의
2. incident queue 표시 방식 정의
3. YOLO frame evidence 연결 방식 정의
4. 관리자 review 입력값 저장 방식 정의

완료 기준:

- `docs/05_operations_feedback/DASHBOARD_INTEGRATION_PLAN.md` 작성

## 7. 아직 답해야 할 질문

1. 1-5월 데이터가 현재 데이터셋 안에 충분한가?
2. 팀원의 YOLO 모델 output 형식은 무엇인가?
3. 대시보드는 어떤 stack으로 만드는가?
4. 실제 사료/음수량 데이터는 얻을 수 있는가?
5. 출하/이동 두수 로그를 받을 수 있는가?
6. CCTV 설치 위치가 돈방별로 얼마나 다른가?
7. 현장 관리자는 어떤 단위의 알림을 가장 편하게 보는가?
8. 프로젝트 표현을 “ASF 진단”으로 할지 “ASF 의심 조기 선별”로 할지 결정해야 한다.

## 8. 결론

현재 방향은 최초 기획과 맞다. 다만 표현은 조정해야 한다. 지금 단계에서 가장 정확한 표현은 “ASF 확진 AI”가 아니라 “돈방 단위 이상징후 조기 선별 및 CCTV 집중분석 지원 시스템”이다.

즉, 지금부터는 상반기 데이터 우선 검증, 돈방 하나 기준 MVP, 성능 지표판, YOLO 결과 스키마, 대시보드 연결 순서로 가는 것이 맞다.
