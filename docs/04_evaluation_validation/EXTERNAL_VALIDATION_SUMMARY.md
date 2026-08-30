# 외부 검증 데이터 역할 정리

## 결론

추가 데이터셋 3개는 메인 학습 데이터에 한꺼번에 섞는 용도가 아닙니다. 현재 프로젝트에서는 각 데이터셋을 서로 다른 질문에 답하는 검증 트랙으로 나눠서 써야 합니다.

| 우선순위 | 데이터셋 | 프로젝트 내 역할 | 현재 판단 |
| --- | --- | --- | --- |
| 1 | HOTPIG | LSTM 이상탐지 파이프라인이 정상과 물리적 스트레스 상태를 구분하는지 확인 | 채택. 단, ASF 증명은 아님 |
| 2 | ASF Dryad challenge | ASF 실제 챌린지에서 체온 규칙의 민감도/정밀도 검증 | 채택. 단, 체온 단독 판정 금지 |
| 3 | Behavior x Heat Tolerance | 행동/근육온도/환경조건 feature profile의 보조 검증 | 보조 근거로만 채택 |
| 4 | AI Hub 71471 | 돼지 행동 라벨 보강 가능성 검토 | 메인 학습 제외, 보조 행동 baseline으로만 유지 |
| 5 | Wearable Stress Biosensor (MDPI Suresh et al.) | 심박/호흡/자세 실측 신호로 격리 스트레스에 대한 파이프라인 반응성 확인 | 채택. 단, ASF 증명은 아님 |
| 6 | PRRSV Play Study | 다른 질병(호흡기) challenge에서 체온 규칙/활동량 규칙 재검증 | 채택. threshold는 생산단계별 재캘리브레이션 필요 확인, ASF 증명은 아님 |

## 3순위 데이터에 대한 결정

Behavior x Heat Tolerance 데이터는 행동만으로 열스트레스가 강하게 탐지된다는 근거로 쓰면 안 됩니다.

- `behavior_only`: HS confirmed anomaly rate 약 2.9%로 낮습니다.
- `behavior_muscle`: HS confirmed anomaly rate 100%입니다.
- `full`: HS confirmed anomaly rate 100%입니다.

즉, 강한 분리는 행동 변화만이 아니라 근육온도와 환경조건 변수의 영향이 큽니다. 따라서 이 데이터는 메인 ASF/활동성 모델 학습에 직접 합치지 않고, 생리적 스트레스가 feature profile에 어떻게 나타나는지 설명하는 보조 검증으로 둡니다.

## 반영 방식

- 메인 모델 학습: 농장/돈방 단위 시간축이 맞는 데이터만 사용합니다.
- 외부 검증: HOTPIG, ASF Dryad, Behavior x Heat Tolerance, AI Hub 71471, Wearable Stress Biosensor, PRRSV Play Study를 별도 산출물로 유지합니다.
- 리포트/발표: “외부 데이터로 모델 반응성, ASF 규칙, 생리적 feature 영향을 각각 점검했다”는 구조로 설명합니다.

## 5순위 데이터에 대한 결정

Wearable Stress Biosensor(MDPI Suresh et al.) 데이터는 돼지 5마리에 부착한 웨어러블 센서로 심박수·호흡수·체온·자세·가속도·ECG를 1초 단위로 측정하고, 격리(Isolation)/짝사육(Pair)을 대조한 실험입니다.

- Pair(정상)만으로 학습한 LSTM Autoencoder가 Pair validation에서는 confirmed anomaly rate 0%를 유지합니다.
- 같은 모델을 학습에 전혀 쓰지 않은 Isolation 구간에 적용하면 confirmed anomaly rate가 39.7%로 뜁니다.
- 즉, HOTPIG(열스트레스)에 이어 사회적 격리라는 별개의 스트레스 유형에서도 같은 파이프라인이 정상과 이상을 구분한다는 두 번째 물리적 스트레스 외부 검증입니다.

상세 내용은 `STRESS_BIOSENSOR_VALIDATION.md`를 참고하세요.

## 6순위 데이터에 대한 결정

PRRSV Play Study는 ASF가 아니라 다른 호흡기 질병(PRRSV) challenge입니다. 이유자돈 30마리를 대상으로 DPI(감염 후 경과일) 기준 체온/임상증상/활동행동/viral load를 기록했습니다.

- ASF Dryad에서 채택한 `rectal_temp_high` threshold(39.5도)를 그대로 적용하면 specificity가 99.5%(ASF)에서 32.9%(PRRSV)로 크게 떨어집니다. 이유자돈의 정상 체온 자체가 육성돈보다 높아서, 절대 온도 임계값은 생산단계별로 다시 잡아야 한다는 걸 확인했습니다.
- 증상이 있는 날은 활동량(active_count)이 15.2% 낮고 비활동량이 20.2% 높습니다 -- `activity_drop` 규칙의 방향성이 다른 질병에서도 같다는 첫 확인입니다.
- 온도 threshold를 어떻게 조정해도 sensitivity가 100%에 가깝지 않다는 결론은 ASF와 PRRSV 양쪽에서 동일하게 성립합니다.

상세 내용은 `PRRSV_EXTERNAL_VALIDATION_REPORT.md`를 참고하세요.

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
