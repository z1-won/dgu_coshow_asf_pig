# 특허 차별점 확보를 위한 프로젝트 수정 계획

작성일: 2026-08-31  
검토 대상 선행특허: 등록특허 `10-2592477` - 돼지 질병 조기진단 장치

## 1. 선행특허 핵심

등록특허 `10-2592477`의 중심은 다음 구조다.

```text
촬영영상/열화상 수신
-> 기학습 AI 모델로 ASF 감염 여부 도출
-> 감염 돼지 인식
-> 마취/이송/소독/소각장 이동 장치 제어
```

상세 설명에서는 코로나 진단용 발열측정기의 열화상/일반 영상 카메라를 재활용하고, 돼지 얼굴, 체온, 반점, 스트레스 지수를 이용해 ASF 감염/비감염을 분류하는 구조가 반복된다.

## 2. 우리 프로젝트가 피해야 할 방향

아래 방향으로 가면 선행특허와 가까워 보일 수 있다.

| 위험 방향 | 왜 위험한가 | 대체 방향 |
| --- | --- | --- |
| "ASF 감염 여부를 영상으로 진단" | 선행특허의 청구항 1, 4와 직접 가까움 | "돈방 단위 이상징후를 센서 시계열로 선별" |
| "열화상/얼굴/반점 기반 ASF 판정" | 선행특허 상세 설명의 핵심 실시예 | "사료/환경/활동/체온 시계열의 정상 이탈 탐지" |
| "YOLO가 감염 돼지를 탐지" | 선행특허의 개별 돼지 감염 판정과 가까움 | "YOLO는 cctv_focus 돈방의 행동/자세 근거 확인" |
| "확진/진단/감염 판정" | 의료/수의학적 판정처럼 보이고 선행특허와 표현 충돌 | "이상 후보, 위험 돈방, 확인 우선순위, triage" |
| "자동 마취/이송/살처분 제어" | 선행특허의 장치 제어부와 직접 겹침 | "관리자 action queue와 확인 로그" |

## 3. 차별점을 강하게 만드는 수정 우선순위

### 1순위: 명칭과 목적 문구 고정

프로젝트 명칭/설명은 다음 표현으로 통일한다.

```text
돈방 단위 이상징후 조기 선별 및 CCTV 집중분석 지원 시스템
```

피할 표현:

```text
돼지 질병 조기진단 장치
ASF 확진 AI
ASF 감염 여부 판정
영상 기반 감염 돼지 탐지
```

이 수정은 기술 내용보다 먼저 필요하다. 문구가 선행특허와 가까우면 실제 구조가 달라도 심사/발표에서 겹쳐 보일 수 있다.

### 2순위: CCTV/YOLO 역할 제한

YOLO는 진단기가 아니라 후속 확인 모듈로 둔다.

```text
센서 scorecard
-> cctv_focus 돈방 선정
-> YOLO 자세/행동 비율 산출
-> 관리자 확인 근거 제공
```

YOLO 출력도 `infected_pig`, `ASF_positive` 같은 컬럼명을 피하고 다음처럼 둔다.

| 권장 컬럼 | 의미 |
| --- | --- |
| `lying_ratio` | 누워있는 비율 |
| `standing_ratio` | 서있는 비율 |
| `feeding_access_count` | 급이기 접근 횟수 |
| `drinking_access_count` | 급수기 접근 횟수 |
| `low_activity_candidate` | 활동 저하 후보 |
| `abnormal_posture_candidate` | 이상 자세 후보 |
| `evidence_frame_path` | 확인용 프레임 경로 |

### 3순위: 농장별 상대 threshold 자동 생성기 구현

가장 강한 기술 차별점이다. 선행특허는 영상/열화상으로 ASF 감염 여부를 도출하는 구조이고, 우리 프로젝트는 농장별 센서 분포로 threshold를 보정한다.

현재 근거:

| 항목 | 고정 기준 문제 | ClearFarm 보정 결과 |
| --- | --- | --- |
| `co2_high` | 1000ppm 기준은 상시 발동 | 2984ppm에서 respiratory F1 43.0% |
| `nh3_high` | 10ppm 기준은 상시 발동 | 29ppm으로 발동 범위 현실화 |
| `barn_temp_high` | 40도 기준은 발동 0건 | 31.6도에서 heat precision 47.5% |
| `feed_drop` | 일단위 z-score로는 발동 불가 | 시간 단위 유지 시 작동 |

구현 방향:

```text
farm calibration input
-> feature distribution by farm/pen/month
-> candidate thresholds by percentile/F1
-> config/domain_rules_{farm}.json 생성
-> scorecard로 검증
```

### 4순위: Disease/Management/Environment 분리 점수 유지

선행특허는 ASF 감염/비감염 판단 중심이다. 우리는 원인을 다음 세 카테고리로 분리한다.

| 카테고리 | 예시 신호 | 목적 |
| --- | --- | --- |
| disease | 체온, 호흡, 행동 이상 | 질병성 의심 |
| management | feed_drop, water_drop | 사양관리/설비 이상 |
| environment | CO2, NH3, barn_temp | 환경/환기 이상 |

차별점은 카테고리를 나누는 데서 끝나지 않고, 동시발생을 `co-occurrence bonus`로 점수화하는 것이다.

```text
rule_score = severity_sum + co_occurrence_bonus
```

현재 구현/근거:

- `src/pigproject/domain_rules.py`
- `src/pigproject/clearfarm_rule_scorecard.py`
- ClearFarm `feed_drop AND co2_high`: precision 46.2%
- 3개 이상 과도 결합 시 tp=0 확인

### 5순위: 3단계 운영 정책을 메인 플로우에 연결

선행특허는 감염 판정 후 장치 제어로 간다. 우리는 진단이 아니라 운영 우선순위로 간다.

| 단계 | 기준 | 행동 |
| --- | --- | --- |
| observe | `rule_score >= 0.3` | 관찰 목록 등록 |
| caution | `rule_score >= 0.6` | 점검 순번 상향 |
| cctv_focus | `rule_score >= 0.9` 또는 `environment_score >= 0.9` | CCTV/YOLO 집중 분석 |

현재 구현/근거:

- `src/pigproject/clearfarm_alert_policy.py`
- `src/pigproject/clearfarm_action_queue_adapter.py`
- `docs/05_operations_feedback/CLEARFARM_3LEVEL_ALERT_POLICY.md`

## 4. 문서 표현 점검 결과

전수 검색 결과, 현재 문서 대부분은 이미 "ASF 확진이 아니다"라는 방어 문구를 포함하고 있다. 그래도 발표/사업계획서/특허 초안에서는 아래처럼 고정한다.

| 현재 사용 가능하지만 조심할 표현 | 권장 표현 |
| --- | --- |
| ASF 의심 조기 선별 | ASF를 포함한 이상징후 조기 선별 |
| 질병 의심도 | 질병성 이상 가능성 점수 |
| 감염 여부 정보 | 사용하지 않음 |
| 질병 진단 | 사용하지 않음 |
| 조기진단 | 단독 사용 금지, "이상징후 조기 선별"로 대체 |

## 5. 바로 손봐야 할 프로젝트 항목

| 우선순위 | 항목 | 상태 | 완료 기준 |
| --- | --- | --- | --- |
| 1 | 선행특허 `10-2592477`을 `PATENT_CANDIDATES.md`에 추가 | 진행 | 선행특허 표와 후보별 차별점에 반영 |
| 2 | 위험 표현 목록 문서화 | 완료 | 본 문서 |
| 3 | 농장별 threshold 자동 생성기 | 미완료 | `config/domain_rules_{farm}.json` 자동 생성 CLI |
| 4 | ClearFarm action queue adapter 마무리 | 진행 | `cctv_requested=True` 전용 YOLO 입력 CSV |
| 5 | YOLO 연동 스키마 문서화 | 미완료 | `docs/07_team_handoff/YOLO_CCTV_INPUT_SCHEMA.md` |

## 6. 결론

차별점 확보의 핵심은 "돼지 질병 조기진단" 경쟁을 피하는 것이다. 우리 프로젝트는 **돈방 단위 센서 시계열 기반 이상징후 triage**로 정의해야 한다. 기술적으로는 농장별 상대 threshold, 카테고리 분리 점수화, 3단계 action queue, CCTV 후속 확인 구조를 강화하는 것이 가장 안전하다.
