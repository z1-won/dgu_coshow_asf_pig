# 외부 검증 데이터 역할 정리

## 결론

추가 데이터셋 3개는 메인 학습 데이터에 한꺼번에 섞는 용도가 아닙니다. 현재 프로젝트에서는 각 데이터셋을 서로 다른 질문에 답하는 검증 트랙으로 나눠서 써야 합니다.

| 우선순위 | 데이터셋 | 프로젝트 내 역할 | 현재 판단 |
| --- | --- | --- | --- |
| 1 | HOTPIG | LSTM 이상탐지 파이프라인이 정상과 물리적 스트레스 상태를 구분하는지 확인 | 채택. 단, ASF 증명은 아님 |
| 2 | ASF Dryad challenge | ASF 실제 챌린지에서 체온 규칙의 민감도/정밀도 검증 | 채택. 단, 체온 단독 판정 금지 |
| 3 | Behavior x Heat Tolerance | 행동/근육온도/환경조건 feature profile의 보조 검증 | 보조 근거로만 채택 |
| 4 | AI Hub 71471 | 돼지 행동 라벨 보강 가능성 검토 | 메인 학습 제외, 보조 행동 baseline으로만 유지 |

## 3순위 데이터에 대한 결정

Behavior x Heat Tolerance 데이터는 행동만으로 열스트레스가 강하게 탐지된다는 근거로 쓰면 안 됩니다.

- `behavior_only`: HS confirmed anomaly rate 약 2.9%로 낮습니다.
- `behavior_muscle`: HS confirmed anomaly rate 100%입니다.
- `full`: HS confirmed anomaly rate 100%입니다.

즉, 강한 분리는 행동 변화만이 아니라 근육온도와 환경조건 변수의 영향이 큽니다. 따라서 이 데이터는 메인 ASF/활동성 모델 학습에 직접 합치지 않고, 생리적 스트레스가 feature profile에 어떻게 나타나는지 설명하는 보조 검증으로 둡니다.

## 반영 방식

- 메인 모델 학습: 농장/돈방 단위 시간축이 맞는 데이터만 사용합니다.
- 외부 검증: HOTPIG, ASF Dryad, Behavior x Heat Tolerance, AI Hub 71471을 별도 산출물로 유지합니다.
- 리포트/발표: “외부 데이터로 모델 반응성, ASF 규칙, 생리적 feature 영향을 각각 점검했다”는 구조로 설명합니다.

상세 산출물은 `artifacts/external_validation_summary/external_validation_summary.md`에서 재생성됩니다.

## 71471 반영 결과

71471은 돼지 keypoints와 행동 라벨(`lying`, `eating`, `standing`, `sitting`)을 제공하므로 행동량 feature 보강 후보로는 의미가 있습니다. 하지만 ASF, 체온, 환경센서 라벨은 없고, 현재 받은 돼지 keypoints 라벨에서는 channel 1-8이 모두 `ESTRUS=Y`, channel 9-16이 모두 `ESTRUS=N`으로 분리되어 있습니다.

따라서 71471은 메인 ASF/돈방 이상탐지 모델에 직접 섞지 않습니다.

현재 실험 결과:

- 71471 annotation rows: `110,960`
- 10분 행동 시계열 bins: `9,644`
- 622 행동량 트랙과 feature mapping: `17/17` 가능
- 71471 전용 행동 baseline 결과: 정상 validation confirmed anomaly `0/46`, 발정 validation confirmed anomaly `0/49`

결론: 71471은 “행동 데이터 확보 및 feature 호환성 확인” 근거로 남기되, “발정 행동이 이상탐지 모델에서 강하게 잡힌다”는 주장에는 사용하지 않습니다.
