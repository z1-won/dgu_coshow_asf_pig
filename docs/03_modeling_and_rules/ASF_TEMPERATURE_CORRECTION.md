# 온도 규칙에 돈사온도 보정 반영

작성일: 2026-08-26
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`

## 1. 왜 필요했나

`rectal_temp_high` 규칙이 원본 `rectal_temperature_mean`을 그대로 40.5도와 비교했다. 그런데 더운 날 돈사 자체 온도가 높으면 건강한 개체도 체온이 살짝 올라갈 수 있다 -- "환경 때문에 높은 것"과 "진짜 발열"을 구분 못 하면 오탐이 늘어난다. 참고한 특허(체표 온도 기반 ASF 감염 의심축 추정, `../03_modeling_and_rules/TEMPERATURE_ONLY_BASELINE_REPORT.md` 2절)도 환경 보정 이후 판단하는 구조를 쓴다.

## 2. 방식

`src/pigproject/domain_rules.py`의 `fit_barn_temp_correction()` / `apply_barn_temp_correction()`:

```text
rectal_corrected = rectal_observed - slope * (T_mean - 26.0)
```

- `slope`: 돈사온도(T_mean) 1도 변화당 직장체온 변화량. 매 `pig-apply-rules` 실행 시 해당 artifact 디렉터리의 `bioenergy_aggregated.csv` 전체(생리적 타당성 필터링 후)로 회귀해서 다시 계산한다. 예전 `../03_modeling_and_rules/TEMPERATURE_ONLY_BASELINE_REPORT.md`의 보정식은 per-pig 집계 수정 이전 값이라 폐기하고 새로 맞췄다.
- `rectal_temp_high` 규칙은 이제 원본이 아니라 `rectal_temperature_mean_corrected`(윈도우 내 최댓값)에 적용된다.
- 계산된 회귀식은 `bioenergy_temp_correction_formula.csv`로 저장되고, `bioenergy_combined_alert_report.md`에도 표시된다.

## 3. 현재 데이터에서 확인된 것

`bioenergy_clean_baseline` 기준 재계산 결과:

```text
rectal_corrected = rectal_observed - (0.004612 * (T_mean - 26.000))
```

- Pearson 상관계수: `0.0058` -- 거의 0.
- 규칙 발생 건수: 보정 전후 동일(19건).

**솔직히 말하면, 지금 데이터에서는 이 보정이 결과를 거의 안 바꾼다.** 돈사온도와 직장체온의 선형관계가 이 데이터셋 안에서 너무 약하기 때문이다(이전 `TEMPERATURE_ONLY_BASELINE_REPORT.md`에서도 이미 "전체 Pearson 상관계수는 약 0.026으로 거의 0에 가깝다"고 같은 결론이었다). 그래도 보정 로직 자체는 맞게 구현됐고, 환경 변동폭이 더 큰 실제 농장 데이터(계절 변화가 뚜렷한 곳)에서는 효과가 더 클 수 있다.

## 4. 해석

이건 "고도화했는데 숫자가 안 바뀌어서 실패"가 아니라, **"이 특정 데이터셋에서는 환경 보정이 필요 없을 만큼 온도가 안정적이었다"는 것도 하나의 결론**이다. 발표에서는 "환경 보정 로직을 구현하고 검증했으며, 현재 검증 데이터에서는 상관관계가 약해 보정 효과가 미미했다 -- 계절 변화가 큰 실제 농장 데이터에서 다시 검증이 필요하다"로 정직하게 설명하는 게 맞다.
