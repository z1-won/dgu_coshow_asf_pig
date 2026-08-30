# ClearFarm 3단계 알림 정책

작성일: 2026-08-30  
근거 산출물: `artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_scored_pen_days.csv`

## 1. 목적

ClearFarm scorecard에서 얻은 `rule_score`, `management_score`, `environment_score`를 실제 운영 행동으로 바꾼다. 이 정책은 ASF 확진 정책이 아니라, 돈방 단위 이상 후보를 어떤 순서로 확인할지 정하는 운영 정책이다.

## 2. 정책 기준

| 단계 | 조건 | 의미 | 다음 행동 |
| --- | --- | --- | --- |
| 1. 관찰 observe | `rule_score >= 0.3` | 단일 저강도 신호 또는 약한 이상 후보 | 관찰 목록 등록, 다음 window 지속 여부 확인 |
| 2. 주의 caution | `rule_score >= 0.6` | 중간 강도 이상 신호, 또는 사료/환경 신호 강화 | 점검 순번 상향, 사료/환경 추세 확인 |
| 3. CCTV 집중 확인 cctv_focus | `rule_score >= 0.9` 또는 `environment_score >= 0.9` | 복합 신호 또는 고확신 환경/고온 후보 | CCTV/YOLO 집중 분석 요청, 필요 시 현장 확인 |
| 정상 normal | 위 조건 없음 | 현재 규칙 점수로는 알림 없음 | 일반 모니터링 유지 |

## 3. ClearFarm 라벨 기준 결과

| 단계 | pen-day 수 | any signs 비율 | respiratory signs 비율 | gut signs 비율 | heat signs 비율 |
| --- | ---: | ---: | ---: | ---: | ---: |
| cctv_focus | 211 | 46.4% | 34.1% | 6.2% | 9.5% |
| caution | 316 | 31.3% | 25.6% | 4.1% | 1.6% |
| observe | 212 | 36.3% | 26.4% | 8.0% | 4.2% |
| normal | 299 | 33.8% | 26.4% | 4.3% | 2.0% |

## 4. 해석

- `cctv_focus`는 `any_signs_rate`가 46.4%로 가장 높아, 집중 확인 단계로 올리는 방향은 맞다.
- `environment_score >= 0.9`는 heat signs 기준 precision 53.1%, specificity 98.5%라 고온/환경성 이상 확인용으로 쓸 수 있다.
- 다만 `normal`의 any signs 비율도 33.8%라서, ClearFarm 건강관찰 라벨만으로는 “normal이면 문제 없음”이라고 말하면 안 된다. 건강관찰은 매일 모든 증상을 정밀 측정한 라벨이 아니라, 관찰일 기록에 가깝다.
- 따라서 이 정책은 최종 진단기가 아니라 **CCTV와 현장 확인 우선순위를 정하는 triage 정책**으로 써야 한다.

## 5. 현재 적용 상태

구현 완료:

- `src/pigproject/clearfarm_alert_policy.py`
- `tests/test_clearfarm_alert_policy.py`
- CLI: `pig-clearfarm-alert-policy`

산출물:

- `artifacts/clearfarm_alert_policy/clearfarm_config/clearfarm_3level_alert_policy.csv`
- `artifacts/clearfarm_alert_policy/clearfarm_config/clearfarm_3level_alert_policy_summary.csv`
- `artifacts/clearfarm_alert_policy/clearfarm_config/clearfarm_3level_alert_policy_report.md`

## 6. 다음 작업

이 정책을 메인 action queue에 연결하려면 ClearFarm 전용 산출물의 컬럼을 `final_chamber_anomaly_scores.csv` 형식(`track_score`, `alert_category`, `tier`, `reason`)으로 변환하는 어댑터가 필요하다. 그 다음 팀원 YOLO 결과와 `cctv_focus` 단계만 연결하면 된다.
