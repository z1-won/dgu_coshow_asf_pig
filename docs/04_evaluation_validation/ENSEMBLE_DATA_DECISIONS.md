# Ensemble 데이터 반영 결정

## 현재 결론

최종 돈방 경보 ensemble에는 현재 `bioenergy`와 `activity_622`만 포함합니다. `71471`은 행동량 보조 검증 트랙으로 유지하고, 메인 ASF/돈방 이상탐지 ensemble에는 넣지 않습니다.

## 데이터셋별 반영 상태

| 데이터셋 | 현재 역할 | ensemble 반영 |
| --- | --- | --- |
| AI Hub 71408/71763 | 생체 에너지, 체온/환경/사양관리 기반 baseline | 포함 |
| AI Hub 622 | 키포인트 행동량 기반 baseline | 포함 |
| HOTPIG | 고온스트레스 외부 sanity check | 미포함, 검증 근거 |
| ASF Dryad challenge | ASF 체온 규칙 검증 | 미포함, 규칙 근거 |
| Behavior x Heat Tolerance | 생리/열스트레스 보조 검증 | 미포함, 보조 근거 |
| AI Hub 71471 | 돼지 행동 라벨 보조 검증 | 미포함, 보조 근거 |

## 71471을 ensemble에서 제외하는 이유

71471은 돼지 keypoints와 행동 라벨을 제공하므로 행동량 feature 보강 후보로는 좋습니다. 하지만 다음 이유 때문에 메인 ensemble에는 넣지 않습니다.

- ASF 라벨, 체온, 환경센서 데이터가 없습니다.
- 현재 받은 돼지 keypoints 라벨은 channel 1-8이 모두 `ESTRUS=Y`, channel 9-16이 모두 `ESTRUS=N`입니다.
- 그래서 발정 효과와 channel/camera 효과가 분리되지 않습니다.
- 71471 전용 행동 baseline에서 발정 validation 구간은 정상 validation보다 강하게 이상으로 잡히지 않았습니다.

## 71471 실험 결과

| 항목 | 값 |
| --- | ---: |
| annotation rows | 110,960 |
| 10분 행동 시계열 bins | 9,644 |
| 622와 매핑 가능한 feature | 17/17 |
| train normal sequences | 3,856 |
| validation normal sequences | 46 |
| validation estrus sequences | 49 |
| normal confirmed anomaly | 0/46 |
| estrus confirmed anomaly | 0/49 |

## 다음 기준

다음 단계는 공개 보조 데이터 추가가 아니라 실제 농장 이벤트 데이터 스키마를 만드는 것입니다. 모델이 실무적으로 의미 있으려면, 동일 돈방에서 센서/행동 시계열과 실제 이벤트가 연결되어야 합니다.
