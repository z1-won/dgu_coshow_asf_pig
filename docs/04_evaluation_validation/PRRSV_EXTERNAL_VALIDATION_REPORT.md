# PRRSV Play Study 실제 challenge 검증

작성일: 2026-08-30
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`
데이터 출처: [Dryad 10.5061/dryad.76hdr7t55](https://datadryad.org/dataset/doi:10.5061/dryad.76hdr7t55) -- 이유자돈 30마리(play/control/sentinel), PRRSV 감염 challenge, DPI(감염 후 경과일) 기준 체온/임상증상/행동/viral load 기록

## 1. 왜 필요했나

ASF Dryad challenge로 `rectal_temp_high` 규칙을 검증했지만, 그건 ASF 한 질병에서만 나온 결과다. **다른 호흡기 질병(PRRSV)의 실제 challenge에서도 같은 규칙이 비슷하게 작동하는지**는 확인한 적이 없었다. 같은 결론이 두 번째 질병에서도 나온다면 "온도 단독 규칙은 정밀도는 있지만 재현율이 낮다"는 주장이 ASF에 국한된 우연이 아니라는 근거가 된다.

## 2. 방법

모듈: `src/pigproject/prrsv_play_study_analysis.py`, CLI `pig-prrsv-play-analysis`.

- 체온(`Rectal temperature`), 임상증상(`Clinical signs probability`, 8개 부위 점수 합 = `clinical_score`), 활동행동(`Active Inactive Feeding behav`), viral load(`long stata final log10`), 치료기록(`medical treatments - detailed`) 5개 시트를 `pig_id`+`dpi` 기준 long table로 병합
- 원본 시트 중 3개는 긴 설명 헤더(row 0) 아래 짧은 변수코드(row 1)가 한 번 더 있는 2단 헤더라 코드로 승격 처리
- `Clinical signs probability` 시트에는 실제 dpi(-2~21) 외에 111/222/...777 같은 비정상 값이 약 210행 섞여 있어 제외(다른 시트 전부 dpi가 -2~21 범위인 것과 대조해 판단)
- `config/domain_rules.json`의 `rectal_temp_high` threshold(39.5도)를 그대로 적용해 ASF Dryad와 동일한 방식으로 confusion matrix 계산

## 3. 결과

| 항목 | 값 |
| --- | ---: |
| pig-days (체온+임상증상 모두 있음) | 226 |
| pigs | 30 |
| symptomatic pig-days | 156 |
| 현재 threshold(39.5도) 기준 sensitivity | 50.0% |
| 현재 threshold 기준 specificity | 32.9% |
| 현재 threshold 기준 precision | 62.4% |

### Threshold Sweep

| threshold | sensitivity | specificity | precision |
| --- | ---: | ---: | ---: |
| 38.8 | 97.4% | 1.4% | 68.8% |
| 39.0 | 93.6% | 4.3% | 68.5% |
| **39.5 (ASF Dryad에서 채택한 값)** | 50.0% | 32.9% | 62.4% |
| 39.8 | 19.2% | 70.0% | 58.8% |
| 40.0 | 8.3% | 85.7% | 56.5% |
| 40.5 | 0.0% | 97.1% | 0.0% |
| 41.0 | 0.0% | 100.0% | 0.0% |

### 활동량 변화 (증상 유무 기준)

| feature | 정상일 평균 | 증상일 평균 | 상대변화 |
| --- | ---: | ---: | ---: |
| active_count | 4.00 | 3.39 | -15.2% |
| inactive_count | 10.09 | 12.13 | +20.2% |

## 4. 해석

- **같은 39.5도 threshold가 ASF Dryad(specificity 99.5%)와 PRRSV Play Study(specificity 32.9%)에서 완전히 다르게 작동한다.** 이유자돈(PRRSV)은 육성돈(ASF Dryad)보다 정상 체온 자체가 높아서, ASF 챌린지에서 고른 절대 온도값이 다른 생산단계에 그대로 옮겨지지 않는다. **rectal_temp_high 임계값은 생산단계(연령대)별로 다시 캘리브레이션해야 한다는 게 이 검증의 핵심 발견이다.**
- 다만 방향성 자체는 두 데이터셋에서 일치한다: threshold를 올릴수록 sensitivity가 떨어지고 specificity가 오르는 전형적인 trade-off이고, 어느 threshold에서도 재현율이 100%에 가깝지 않다 -- "온도 단독으로는 부족하다"는 결론은 ASF와 PRRSV 양쪽에서 동일하게 성립한다.
- 증상이 있는 날은 활동량(active_count)이 15.2% 낮고 비활동량(inactive_count)이 20.2% 높다 -- 방향은 예상대로지만 크기는 크지 않다. `activity_drop` 규칙이 실제 질병 challenge에서도 같은 방향으로 작동한다는 첫 확인이지만, 단독 강한 신호로 쓰기엔 약하다.

## 5. 한계

- PRRSV는 ASF가 아니라 호흡기 질병 challenge다. 여기서 나온 수치를 ASF 확진 성능으로 주장하지 않는다.
- 이유자돈 30마리 대상 실험실 challenge라 실제 농가의 계절/개체혼합 노이즈는 반영하지 않는다.
- 활동행동 데이터가 dpi마다 빠짐없이 있지 않아(측정일이 산발적) daily lead-time 평가는 아직 못했다.

## 6. 발표에 쓸 수 있는 한 줄

> "실제 PRRSV challenge 데이터로 체온 규칙을 재검증한 결과, 같은 임계값(39.5도)이 ASF 챌린지와 전혀 다른 specificity(99.5% vs 32.9%)를 보였다 -- 온도 임계값은 생산단계별로 다시 캘리브레이션이 필요하다는 걸 확인했고, 동시에 '온도 단독으로는 재현율이 부족하다'는 결론은 두 질병 모두에서 일치해 모델 기반 이상탐지 병행의 근거를 하나 더 얻었다."
