# 실제 농장 이벤트 데이터 스키마

목적: 최종 anomaly 경보가 실제 농장 사건 근처에서 발생했는지 검증하기 위한 최소 이벤트 로그 형식이다. 이 파일은 모델 입력 데이터가 아니라, 모델 결과를 평가하고 운영 기준을 조정하기 위한 정답/운영 기록에 가깝다.

## 필수 컬럼

| 컬럼 | 의미 | 예시 |
| --- | --- | --- |
| `event_id` | 사건 고유 ID | `evt-0001` |
| `farm_id` | 농장 ID | `farm-a` |
| `chamber_id` | 모델 경보 테이블과 맞출 돈방 ID | `bioenergy:71408:1` |
| `event_type` | 사건 종류 | `fever` |
| `start_datetime` | 사건 시작 시각 | `2023-01-01 08:00:00` |
| `end_datetime` | 사건 종료 시각 | `2023-01-01 18:00:00` |
| `severity` | 심각도 1~5 | `3` |
| `vet_confirmed` | 수의사/관리자 확인 여부 | `true` 또는 `false` |
| `source` | 기록 출처 | `farm_log`, `vet_record`, `sensor_note` |
| `notes` | 자유 메모 | `발열 관찰, 투약 전` |

## 허용 event_type

`asf_suspected`, `asf_confirmed`, `fever`, `respiratory`, `feed_drop`, `water_drop`, `mortality`, `treatment`, `vaccination`, `environment_failure`, `equipment_failure`, `movement`, `other`

## 사용 방법

템플릿만 생성:

```bash
pig-farm-events
```

실제 이벤트 CSV 검증 및 최종 경보와 매칭:

```bash
pig-farm-events \
  --input data/raw/farm_events/farm_event_log.csv \
  --alerts-csv data/processed/final_chamber_anomaly_scores.csv
```

lead-time 기준을 바꾸고 싶으면 시간 단위로 지정한다:

```bash
pig-farm-events \
  --input data/raw/farm_events/farm_event_log.csv \
  --alerts-csv data/processed/final_chamber_anomaly_scores.csv \
  --lead-hours 24,48,72
```

생성 산출물:

- `data/templates/farm_event_log_template.csv`
- `data/processed/farm_event_log_clean.csv`
- `artifacts/farm_event_schema_issues.csv`
- `artifacts/farm_event_alert_matches.csv`
- `artifacts/farm_event_lead_time_matches.csv`
- `artifacts/farm_event_lead_time_summary.csv`
- `artifacts/farm_event_schema_report.md`

## 해석 기준

- `schema error`가 0이어야 평가용 데이터로 쓸 수 있다.
- `farm_event_alert_matches.csv`는 같은 `chamber_id`에서 이벤트 시간과 최종 alert window가 겹친 경우만 기록한다.
- `farm_event_lead_time_matches.csv`는 이벤트 시작 전 24/48/72시간 안에 같은 `chamber_id`에서 먼저 발생한 alert를 기록한다.
- `farm_event_lead_time_summary.csv`는 이벤트별 최초 사전 경보 시각, lead time, horizon별 포착 여부를 기록한다.
- 매칭이 많으면 경보가 실제 사건 근처에서 반응했다는 근거가 된다.
- 매칭이 거의 없으면 시간 단위, chamber_id 매핑, event_type 정의, threshold를 다시 확인해야 한다.
- lead-time recall은 사건 기준으로 “사건 전에 경보가 먼저 떴는가”를 보는 값이다.
- precision proxy는 전체 alert window 중 이벤트 사전 경보로 연결된 window 비율이다. 실제 운영 precision과 비슷하게 해석할 수 있지만, 실제 미기록 사건이 있으면 낮게 보일 수 있다.

## 지금 프로젝트에서 가장 중요한 점

현재 AI Hub 데이터는 실제 ASF 확진 이벤트 로그가 붙어 있지 않다. 따라서 모델 성능을 “정확도”로 말하기 어렵고, 지금은 이상 후보를 합리적으로 선별하는 파이프라인 검증 단계다. 실제 농장 이벤트 로그가 들어오면 이 스키마로 정리한 뒤, 경보 window와 시간 겹침을 계산해 precision/recall에 가까운 운영 지표로 넘어갈 수 있다.
