# 행동 taxonomy 비교: 622 트랙 vs Multimodal Wearable vs 대시보드

작성일: 2026-08-30

## 1. 목적

프로젝트 안에 "행동(behavior)"을 가리키는 라벨 체계가 세 군데 흩어져 있었다 — (1) AI Hub 622 원본 라벨(카메라 키포인트), (2) 622 모델이 실제로 입력 feature로 쓰는 부분집합, (3) 방금 받은 Pig Multimodal Wearable Dataset의 4-class. 대시보드의 "인식 가능한 행동" 목록은 화이트보드 스케치를 그대로 옮긴 것이라 이 셋 중 어느 것과도 검증 없이 붙어 있었다. 이 문서는 그 셋을 실제 코드/데이터 기준으로 나란히 놓고, 대시보드 표기를 맞춘다.

## 2. 622 원본 라벨 (`src/pigproject/activity_features.py`)

`BEHAVIOR_LABELS` 14개: Lying, Standing, Walking, Running, Eating, Drinking, Suckling, Searching, Scrubbing, Urinating, Defecating, Sitting, Resting, Parturition.

두 그룹으로 축약:
- `ACTIVE_LABELS = {Walking, Running, Searching, Scrubbing, Eating, Drinking}`
- `REST_LABELS = {Lying, Resting, Sitting}`

## 3. 622 모델이 실제로 쓰는 feature (`activity_model_dataset.DEFAULT_FEATURE_COLUMNS`)

14개 원본 라벨 중 **개별 ratio/count feature로 모델에 들어가는 건 6개뿐**: `lying`, `standing`, `walking`, `running`, `suckling`, `searching`.

**Eating과 Drinking은 개별 feature가 아니다** — `active_behavior_ratio`(Walking+Running+Searching+Scrubbing+Eating+Drinking 합산)에 다른 4개 라벨과 섞여서만 들어간다. Sitting과 Resting도 마찬가지로 `rest_behavior_ratio`(Lying+Resting+Sitting 합산)에만 섞여 있다. 즉 지금 모델은 "돼지가 먹고 있는지"를 개별 신호로 구분하지 못한다 — 활동 중이라는 것만 안다.

## 4. Pig Multimodal Wearable Dataset (Zenodo 20370059)

4-class: lying, eating, walking, drinking (`label_dictionary.csv` 기준). lying은 원 데이터의 deitadoac(누워서 깸)+dormindo(수면)를 합친 것 — 622의 REST_LABELS가 여러 원시 라벨을 묶는 방식과 구조적으로 유사하다.

## 5. 세 taxonomy 대조표

| 622 원본 라벨 | 622 모델 feature | Multimodal 4-class | 대시보드 표기(수정 전) |
| --- | --- | --- | --- |
| Lying | `lying_ratio` (개별) | lying | 누워 있음 |
| Standing | `standing_ratio` (개별) | - | 서 있음 |
| Walking | `walking_ratio` (개별) | walking | 이동 |
| Running | `running_ratio` (개별) | - | - |
| Suckling | `suckling_ratio` (개별) | - | - |
| Searching | `searching_ratio` (개별) | - | - |
| Eating | `active_behavior_ratio`에 합산 | eating | 급이(먹기) |
| Drinking | `active_behavior_ratio`에 합산 | drinking | 급수(마시기) |
| Sitting | `rest_behavior_ratio`에 합산 | - | 앉아 있음 |
| Resting | `rest_behavior_ratio`에 합산 | - | - |
| Scrubbing/Urinating/Defecating/Parturition | 미사용 | - | - |

## 6. 발견한 문제

대시보드(`dashboard/src/App.jsx`, `sensorProfile`)의 카메라 트랙 "인식 가능한 행동" 목록이 **화이트보드를 그대로 옮긴 것**이라 622 모델이 실제로 구분하는 6개 개별 feature(Lying/Standing/Walking/Running/Suckling/Searching)와 다르다. 특히 "급이(먹기)"/"급수(마시기)"는 모델이 개별 신호로 구분하지 못하는데도 마치 구분되는 것처럼 표기돼 있었다 — 관리자에게 실제 모델 능력보다 과장된 인상을 줄 수 있다.

## 7. 조치

`dashboard/src/App.jsx`의 `sensorProfile`을 622 모델이 실제로 구분하는 6개 라벨(Lying/Standing/Walking/Running/Suckling/Searching) + "활동/휴식 비율(급이·급수 등 포함)" 한 줄로 교체 예정 — 실제 모델 출력과 어긋나지 않게.

## 8. Multimodal 데이터셋의 위치

Multimodal Wearable Dataset은 622와 taxonomy 구조는 비슷하지만(REST 그룹핑 철학 유사) 센서 자체가 다르고(웨어러블 가속도+오디오 vs 카메라 키포인트), pen 매핑도 없다. 지금 단계에서는 622 모델을 검증할 정답지로 쓸 수 없고, "이런 taxonomy 그룹핑이 다른 연구에서도 쓰인다"는 참고 근거 정도로만 유효하다.
