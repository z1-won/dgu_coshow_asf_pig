# 실제 ASF 챌린지 데이터로 온도 규칙 검증

작성일: 2026-08-26
프로젝트 경로: `/Users/bangjiwon/dev/pigproject`
데이터 출처: Lotonin et al., *Correlates of protection against African swine fever virus identified by a systems immunology approach*, [Dryad 10.5061/dryad.cnp5hqcm5](https://datadryad.org/dataset/doi:10.5061/dryad.cnp5hqcm5)

## 1. 왜 필요했나

지금까지 `rectal_temp_high`(≥40.5도) 규칙은 AI Hub의 "정상으로 가정한" 데이터에서만 확인했다. HotPig(열스트레스)로 모델의 반응성은 검증했지만, **진짜 ASF에 대한 온도 규칙의 민감도/특이도는 한 번도 측정한 적이 없었다.**

이 데이터셋은 돼지 10마리(농장돼지 5, SPF돼지 5)에게 실제 고병원성 ASFV(Armenia 2008 genotype II)를 공격접종한 백신 챌린지 스터디다. day -3부터 +25까지 **일별 직장체온과, 발적/식욕부진/무기력 등 9개 항목을 0-3점으로 채점한 임상점수**가 함께 기록되어 있다. 임상점수는 연구진이 직접 관찰해 매긴 것이라, "이 날 이 개체가 증상이 있었는가"에 대한 실제 정답으로 쓸 수 있다.

## 2. 방법

`scripts/verify_rectal_temp_rule_against_real_asf.py`. 돼지 10마리 x 관측일 = 226 pig-day에 대해:
- `rule_fires = rectal_temp >= 40.5`
- `symptomatic = clinical_score > 0`

두 이진값의 confusion matrix를 계산했다.

추가 종합 분석 모듈도 만들었다: `src/pigproject/asf_dryad_analysis.py`, CLI `pig-asf-dryad-analysis`.
이 모듈은 `Fig. 1F`의 실제 challenge 온도/임상점수에 `Fig. 1H` 혈중 viral load, `Sup. Fig. 3` leukocyte를 병합해 다음 산출물을 만든다.

- `artifacts/asf_dryad_validation/asf_dryad_validation_report.md`
- `artifacts/asf_dryad_validation/asf_challenge_daily_long.csv`
- `artifacts/asf_dryad_validation/asf_rectal_temp_threshold_sweep.csv`
- `artifacts/asf_dryad_validation/asf_per_pig_timeline.csv`
- `artifacts/asf_dryad_validation/asf_daily_summary.csv`

## 3. 결과

| | symptomatic (실제 증상 있음) | asymptomatic (실제 정상) |
| --- | ---: | ---: |
| rule_fires | TP = 16 | FP = **0** |
| rule 안 걸림 | FN = 23 | TN = 187 |

- **특이도(specificity) = 100%**: 226 pig-day 중 규칙이 오탐한 경우가 **단 한 번도 없었다.** 규칙이 걸리면 예외 없이 실제 증상이 있는 날이었다.
- **정밀도(precision) = 100%**: 같은 이유로, "이 규칙이 울리면 믿을 수 있다"가 이 데이터에서는 100% 성립한다.
- **재현율(sensitivity) = 41.0%**: 다만 증상이 있는 날 중 59%는 40.5도를 넘지 않아서 놓쳤다.

### 개체별 발병 시점 대비 규칙 발동 시점

| 개체 | 첫 증상일 | 첫 규칙발동일 | 지연 | 최고 임상점수 |
| --- | ---: | ---: | ---: | ---: |
| Farm #13 | 6 | 6 | 0 | 17 (중증) |
| Farm #15 | 5 | 5 | 0 | 14 (중증) |
| Farm #17 | 5 | 6 | 1 | 15 (중증) |
| SPF #1967 | 7 | 7 | 0 | 8 (중등) |
| Farm #16 | 6 | 10 | 4 | 7 (중등) |
| Farm #14 | 6 | 안 걸림 | - | 7 (중등) |
| SPF #1973 | 5 | 안 걸림 | - | 1 (경증) |
| SPF #1974 | 3 | 안 걸림 | - | 1 (경증) |
| SPF #1963/1966 | 증상 없음 | 안 걸림 | - | 0 |

**패턴이 뚜렷하다: 최고 임상점수가 높은(중증) 개체는 증상 발현 당일~1일 이내에 규칙이 걸리고, 점수가 낮은(경증) 개체는 늦게 걸리거나 아예 안 걸린다.**

## 4. 해석

1. **온도 단독 규칙은 "걸리면 확실하다"는 신뢰도(정밀도 100%)를 갖지만, 초기/경증 증상은 구조적으로 놓친다(재현율 41%).** 발열이 임상적으로 뚜렷해지는 시점(대개 중등도 이상)에야 40.5도를 넘기 때문이다.
2. **이게 바로 모델(LSTM anomaly) + 규칙을 같이 쓰는 이유를 실증한다.** 규칙 하나로는 절반 넘는 증상일을 놓치므로, 온도가 아직 임계값 아래일 때의 미세한 패턴 변화(행동, 사료/음수 등)를 보는 모델 쪽 신호가 반드시 필요하다.
3. 경증 개체(SPF #1973, #1974, 최고 점수 1점)는 애초에 온도로 잡을 만한 증상이 아니었을 수 있다 -- 이런 케이스가 domain_rules의 `feed_drop`/`water_spike` 같은 비-온도 규칙이 존재하는 이유와도 맞아떨어진다.

## 5. 한계

- 개체 수가 10마리(226 pig-day)로 작다. 특이도 100%가 통계적으로 완벽히 안정된 수치라고 보기는 어렵다.
- 이 실험은 통제된 챌린지 스터디(실험실)라 실제 농장 환경의 노이즈(계절, 다개체 혼합 등)를 반영하지 않는다.
- 이 데이터에는 사료/음수 데이터가 없어서 `feed_drop`/`water_spike` 규칙이나 disease_score의 동시발생 보너스는 검증하지 못했다 -- 온도 규칙 단독 성능만 확인 가능했다.

## 6. Threshold 재조정 (재현율 41%는 낮다는 지적 이후)

40.5도는 원래 ASF 매뉴얼의 "초기 고열 41~42도"를 보수적으로 낮춘 값이었는데, 실제 데이터로 스윕해보니 더 낮출 여지가 있었다.

| threshold | 재현율 | 특이도 | 정밀도 | FP |
| --- | ---: | ---: | ---: | ---: |
| 38.8 | 59.0% | 96.8% | 79.3% | 6 |
| 39.0 | 48.7% | 98.9% | 90.5% | 2 |
| **39.5 (채택)** | **48.7%** | **99.5%** | **95.0%** | **1** |
| 39.8 | 46.2% | 99.5% | 94.7% | 1 |
| 40.0 | 43.6% | 99.5% | 94.4% | 1 |
| 40.5 (이전 기본값) | 41.0% | 100.0% | 100.0% | 0 |
| 41.0 | 23.1% | 100.0% | 100.0% | 0 |

`config/domain_rules.json`의 `rectal_temp_high` threshold를 **40.5 -> 39.5**로 낮췄다. 226 pig-day 중 오탐이 1건 늘어나는 대신(0->1) 재현율이 41.0% -> 48.7%로 오른다 -- 이 정도 손해면 바꿀 만하다고 판단했다.

38.8도까지 더 낮추면 재현율이 59%까지 오르지만 정밀도가 79.3%로 급락한다(FP 6건). **어느 threshold를 골라도 재현율이 60%를 넘지 못한다는 게 핵심이다** -- 단일 시점 절대 온도값만으로 잡을 수 있는 상한이 이 근처라는 뜻이고, 나머지는 모델(disease_score의 model_component) 쪽이 메워야 하는 몫이다.

AI Hub 데이터에 적용했을 때 영향은 작다: `bioenergy_clean_baseline` 기준 rule anomaly가 19 -> 20건으로 1건만 늘었다 (71763은 직장체온이 38.9도를 넘은 적이 없어서 이 조정의 영향을 아예 안 받는다).

39.5도 기준으로 다시 보면 SPF #1967은 첫 증상일(day 7)보다 하루 **먼저**(day 6) 규칙이 걸렸다 -- 이 개체 한정으로는 임상 관찰보다 온도가 먼저 반응한 사례다.

## 7. 발표에 쓸 수 있는 한 줄

> "실제 ASF 챌린지 스터디(공개 데이터, Dryad)로 온도 규칙 threshold를 스윕 검증해 40.5도에서 39.5도로 조정했다. 정밀도 95%(오탐 1/226)를 유지하면서 재현율을 41%에서 49%로 끌어올렸고, 그럼에도 단일 온도값만으로는 재현율이 60%를 넘지 못한다는 구조적 한계를 확인해 모델 기반 이상탐지를 함께 쓰는 근거로 삼았다."

## 8. Dryad 종합 분석 결과

`pig-asf-dryad-analysis`로 실제 challenge 구간을 다시 병합해 확인했다.

- 39.5도 기준: TP 19, FN 20, FP 1, TN 186
- sensitivity 48.7%, specificity 99.5%, precision 95.0%
- 중증 개체(Farm #13, #15, #17)는 첫 증상일과 같은 날 온도 규칙이 발동했다.
- SPF #1967은 첫 증상일(day 7)보다 하루 전(day 6)에 온도 규칙이 먼저 발동했다.
- Farm #14, SPF #1973처럼 임상점수는 있지만 온도 규칙/viral load가 뚜렷하지 않은 개체도 있었다.

해석: ASF Dryad는 온도 규칙의 정밀도는 강하게 지지하지만, 단일 온도 규칙만으로는 경증/일부 중등 증상을 놓친다. viral load와 leukocyte는 ASF 특이성이 높지만 현재 돈방 IoT 입력에는 없으므로, 조기 선별 모델의 입력이 아니라 확진/수의검사 단계의 보조 근거로 분리하는 게 맞다.
