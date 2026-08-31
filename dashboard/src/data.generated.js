// 이 파일은 dashboard/scripts/generate-dashboard-data.mjs가 생성합니다.
// 입력: artifacts/final_chamber_summary.csv, artifacts/action_queues/incident_queue.csv

export const CHAMBERS = [
  {
    "id": "bioenergy:71408:4",
    "buildingLabel": "1동",
    "code": "bioenergy:71408:4",
    "room": "4번 돈방",
    "track": "체온·환경 센서",
    "windows": 10,
    "mean": 1.2506,
    "max": 1.3705,
    "modelTier": "medium",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "71408",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "1동",
      "comparedPens": 3,
      "meanMaxScore": 0.9668,
      "deltaFromBarnMean": 0.4037,
      "maxScoreRank": 1
    },
    "operationalStage": {
      "key": "cctv_focus",
      "label": "CCTV 확인",
      "priorityLabel": "CCTV 확인",
      "description": "고확신 이상 또는 환경 점수 상승"
    }
  },
  {
    "id": "bioenergy:71408:2",
    "buildingLabel": "1동",
    "code": "bioenergy:71408:2",
    "room": "2번 돈방",
    "track": "체온·환경 센서",
    "windows": 10,
    "mean": 1.2903,
    "max": 1.3258,
    "modelTier": "medium",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "71408",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "1동",
      "comparedPens": 3,
      "meanMaxScore": 0.9668,
      "deltaFromBarnMean": 0.359,
      "maxScoreRank": 2
    },
    "operationalStage": {
      "key": "cctv_focus",
      "label": "CCTV 확인",
      "priorityLabel": "CCTV 확인",
      "description": "고확신 이상 또는 환경 점수 상승"
    }
  },
  {
    "id": "activity622:facility3:pen7",
    "buildingLabel": "3동",
    "code": "activity622:facility3:pen7",
    "room": "3구역 7번방",
    "track": "카메라 행동분석",
    "windows": 3,
    "mean": 0.4893,
    "max": 0.5231,
    "modelTier": "normal",
    "lowConf": true,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": 0.4213,
      "maxScoreRank": 1
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "bioenergy:71763:2",
    "buildingLabel": "2동",
    "code": "bioenergy:71763:2",
    "room": "2번 돈방",
    "track": "체온·환경 센서",
    "windows": 10,
    "mean": 0.4033,
    "max": 0.5136,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "71763",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "2동",
      "comparedPens": 3,
      "meanMaxScore": 0.3987,
      "deltaFromBarnMean": 0.1149,
      "maxScoreRank": 1
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "bioenergy:71763:3",
    "buildingLabel": "2동",
    "code": "bioenergy:71763:3",
    "room": "3번 돈방",
    "track": "체온·환경 센서",
    "windows": 10,
    "mean": 0.4063,
    "max": 0.4876,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "71763",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "2동",
      "comparedPens": 3,
      "meanMaxScore": 0.3987,
      "deltaFromBarnMean": 0.0889,
      "maxScoreRank": 2
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "bioenergy:71408:1",
    "buildingLabel": "1동",
    "code": "bioenergy:71408:1",
    "room": "1번 돈방",
    "track": "체온·환경 센서",
    "windows": 6,
    "mean": 0.1933,
    "max": 0.2042,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "71408",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "1동",
      "comparedPens": 3,
      "meanMaxScore": 0.9668,
      "deltaFromBarnMean": -0.7626,
      "maxScoreRank": 3
    },
    "operationalStage": {
      "key": "caution",
      "label": "확인 필요",
      "priorityLabel": "확인 필요",
      "description": "담당자 점검 순번 상향"
    }
  },
  {
    "id": "bioenergy:71763:1",
    "buildingLabel": "2동",
    "code": "bioenergy:71763:1",
    "room": "1번 돈방",
    "track": "체온·환경 센서",
    "windows": 15,
    "mean": 0.183,
    "max": 0.1948,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "71763",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "2동",
      "comparedPens": 3,
      "meanMaxScore": 0.3987,
      "deltaFromBarnMean": -0.2039,
      "maxScoreRank": 3
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility3:pen6",
    "buildingLabel": "3동",
    "code": "activity622:facility3:pen6",
    "room": "3구역 6번방",
    "track": "카메라 행동분석",
    "windows": 17,
    "mean": 0.0955,
    "max": 0.1296,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": 0.0278,
      "maxScoreRank": 2
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility3:pen1",
    "buildingLabel": "3동",
    "code": "activity622:facility3:pen1",
    "room": "3구역 1번방",
    "track": "카메라 행동분석",
    "windows": 5,
    "mean": 0.062,
    "max": 0.0632,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.0386,
      "maxScoreRank": 3
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility3:pen8",
    "buildingLabel": "3동",
    "code": "activity622:facility3:pen8",
    "room": "3구역 8번방",
    "track": "카메라 행동분석",
    "windows": 3,
    "mean": 0.0446,
    "max": 0.0491,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.0527,
      "maxScoreRank": 4
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility5:pen4",
    "buildingLabel": "3동",
    "code": "activity622:facility5:pen4",
    "room": "5구역 4번방",
    "track": "카메라 행동분석",
    "windows": 6,
    "mean": 0.0402,
    "max": 0.0426,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.0592,
      "maxScoreRank": 5
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility3:pen5",
    "buildingLabel": "3동",
    "code": "activity622:facility3:pen5",
    "room": "3구역 5번방",
    "track": "카메라 행동분석",
    "windows": 11,
    "mean": 0.0277,
    "max": 0.0399,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.0619,
      "maxScoreRank": 6
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility5:pen3",
    "buildingLabel": "3동",
    "code": "activity622:facility5:pen3",
    "room": "5구역 3번방",
    "track": "카메라 행동분석",
    "windows": 3,
    "mean": 0.0346,
    "max": 0.0354,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.0664,
      "maxScoreRank": 7
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility1:pen7",
    "buildingLabel": "3동",
    "code": "activity622:facility1:pen7",
    "room": "1구역 7번방",
    "track": "카메라 행동분석",
    "windows": 8,
    "mean": 0.0166,
    "max": 0.0176,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.0842,
      "maxScoreRank": 8
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  },
  {
    "id": "activity622:facility3:pen2",
    "buildingLabel": "3동",
    "code": "activity622:facility3:pen2",
    "room": "3구역 2번방",
    "track": "카메라 행동분석",
    "windows": 14,
    "mean": 0.013,
    "max": 0.0158,
    "modelTier": "normal",
    "lowConf": false,
    "evidence": {
      "sourceCsv": "artifacts/final_chamber_summary.csv",
      "sourceDataset": "622",
      "scoreFields": [
        "mean_score",
        "max_score",
        "chamber_tier",
        "operational_alert_windows"
      ],
      "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
      "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보"
    },
    "barnComparison": {
      "scope": "3동",
      "comparedPens": 9,
      "meanMaxScore": 0.1018,
      "deltaFromBarnMean": -0.086,
      "maxScoreRank": 9
    },
    "operationalStage": {
      "key": "normal",
      "label": "정상",
      "description": "확인 필요 이벤트 없음"
    }
  }
];

export const NO_DATA_ROOMS = [
  {
    "id": "bioenergy:71408:3-nodata",
    "buildingLabel": "1동",
    "code": "bioenergy:71408:3",
    "room": "3번 돈방",
    "note": "관측 횟수 부족(19회, 최소 24회 필요)으로 분석 대상에서 제외됨",
    "isNoData": true,
    "operationalStage": {
      "key": "nodata",
      "label": "데이터 부족",
      "description": "수집 기준 미달"
    }
  }
];

export const BUILDINGS = [
  "1동",
  "2동",
  "3동"
];
export const FARM_SCOPE = {
  "farmId": "demo-farm",
  "farmName": "시연 농장",
  "mode": "single_farm",
  "description": "운영 제품에서는 로그인한 농장의 돈사/돈방만 표시"
};
export const TOTAL_ROOMS = CHAMBERS.length + NO_DATA_ROOMS.length;

export const INCIDENTS = [
  {
    "id": "disease-0001",
    "chamberId": "bioenergy:71408:4",
    "category": "disease",
    "start": "2022-11-23",
    "end": "2022-12-05",
    "windows": 10,
    "score": 1.3705,
    "reasonParts": [
      "체온 상승",
      "이산화탄소 농도 상승"
    ],
    "action": "체온 상승 개체 확인, 증상 관찰, 격리 필요성 판단, 수의사 확인",
    "operationalStage": {
      "key": "cctv_focus",
      "label": "CCTV 확인",
      "priorityLabel": "CCTV 확인",
      "description": "고확신 이상 또는 환경 점수 상승"
    },
    "environmentTemp": {
      "policy": "",
      "label": "",
      "action": ""
    },
    "evidence": {
      "sourceCsv": "artifacts/action_queues/incident_queue.csv",
      "rawReason": "rule: disease: rectal_temp_high | environment: co2_high",
      "scoreField": "max_track_score",
      "scoreFormula": "질병 큐: 체온·행동 이상 점수 우선",
      "inputScores": {
        "track": 1.3705,
        "management": 0,
        "environment": 0.3
      },
      "decisionRule": "domain rule이 감지한 이벤트를 action queue로 승격"
    }
  },
  {
    "id": "disease-0002",
    "chamberId": "bioenergy:71408:2",
    "category": "disease",
    "start": "2022-12-08",
    "end": "2022-12-20",
    "windows": 10,
    "score": 1.3258,
    "reasonParts": [
      "체온 상승"
    ],
    "action": "체온 상승 개체 확인, 증상 관찰, 격리 필요성 판단, 수의사 확인",
    "operationalStage": {
      "key": "cctv_focus",
      "label": "CCTV 확인",
      "priorityLabel": "CCTV 확인",
      "description": "고확신 이상 또는 환경 점수 상승"
    },
    "environmentTemp": {
      "policy": "",
      "label": "",
      "action": ""
    },
    "evidence": {
      "sourceCsv": "artifacts/action_queues/incident_queue.csv",
      "rawReason": "rule: disease: rectal_temp_high",
      "scoreField": "max_track_score",
      "scoreFormula": "질병 큐: 체온·행동 이상 점수 우선",
      "inputScores": {
        "track": 1.3258,
        "management": 0,
        "environment": 0
      },
      "decisionRule": "domain rule이 감지한 이벤트를 action queue로 승격"
    }
  },
  {
    "id": "environment-0001",
    "chamberId": "bioenergy:71408:1",
    "category": "environment",
    "start": "2022-11-17",
    "end": "2022-12-31",
    "windows": 6,
    "score": 0.9,
    "reasonParts": [
      "이산화탄소 농도 상승",
      "암모니아 농도 상승"
    ],
    "action": "환기량 증대, CO2/NH3 센서 재확인, 분뇨/환기 설비 점검",
    "operationalStage": {
      "key": "caution",
      "label": "확인 필요",
      "priorityLabel": "확인 필요",
      "description": "담당자 점검 순번 상향"
    },
    "environmentTemp": {
      "policy": "",
      "label": "",
      "action": ""
    },
    "evidence": {
      "sourceCsv": "artifacts/action_queues/incident_queue.csv",
      "rawReason": "rule: environment: co2_high,nh3_high",
      "scoreField": "max_environment_score",
      "scoreFormula": "환경 큐: CO2/NH3/환기 점수 우선",
      "inputScores": {
        "track": 0.2042,
        "management": 0,
        "environment": 0.9
      },
      "decisionRule": "domain rule이 감지한 이벤트를 action queue로 승격"
    }
  }
];

export const PERFORMANCE_SUMMARY = {
  "sourceFiles": [
    "artifacts/clearfarm_rule_scorecard/clearfarm_config/clearfarm_rule_score_threshold_sweep.csv",
    "artifacts/clearfarm_rule_scorecard/recall_candidate_config/clearfarm_recall_candidate_summary.csv",
    "artifacts/clearfarm_rule_scorecard/jan_may_candidate_config/clearfarm_jan_may_candidate_vs_configs.csv",
    "artifacts/clearfarm_precision_tuning/full_recall_candidate/clearfarm_precision_policy_metrics.csv",
    "artifacts/clearfarm_alert_policy/precision_tuned_recall_candidate/clearfarm_3level_alert_policy_summary.csv",
    "artifacts/clearfarm_environment_policy_experiment/clearfarm_environment_policy_comparison.csv",
    "artifacts/category_lead_time_metrics.csv",
    "artifacts/external_validation_summary/external_validation_summary.csv"
  ],
  "headline": [
    {
      "label": "ClearFarm 조기 선별",
      "value": 73.1,
      "unit": "민감도",
      "detail": "rule_score >= 0.3 · 정밀도 37.1% · F1 49.2%",
      "caution": "알림 수가 많아 1차 선별용"
    },
    {
      "label": "ClearFarm 고확신 알림",
      "value": 46.4,
      "unit": "정밀도",
      "detail": "rule_score >= 0.9 · 특이도 83% · 민감도 26.1%",
      "caution": "놓치는 사건이 많아 단독 운영 불가"
    },
    {
      "label": "사전 경보 포착",
      "value": 50,
      "unit": "24시간 recall",
      "detail": "6개 이벤트 중 3개 사전 포착 · 48/72시간도 50%/50%",
      "caution": "현재는 synthetic event 기준"
    },
    {
      "label": "ASF 체온 rule",
      "value": 95,
      "unit": "정밀도",
      "detail": "rectal_temp_high 39.5C: sensitivity 48.7%, specificity 99.5%, precision 95.0%",
      "caution": "체온 단독 진단으로 쓰지 않음"
    }
  ],
  "clearfarmRows": [
    {
      "label": "조기 선별",
      "threshold": "rule_score >= 0.3",
      "n": 1038,
      "alerts": 739,
      "sensitivity": 73.1,
      "specificity": 29.9,
      "precision": 37.1,
      "f1": 49.2
    },
    {
      "label": "고확신 알림",
      "threshold": "rule_score >= 0.9",
      "n": 1038,
      "alerts": 211,
      "sensitivity": 26.1,
      "specificity": 83,
      "precision": 46.4,
      "f1": 33.4
    }
  ],
  "environmentPolicy": [
    {
      "policy": "screening",
      "label": "선별",
      "threshold": "28.7°C",
      "alerts": 196,
      "recall": 92.5,
      "precision": 18.9,
      "specificity": 78.5,
      "falseAlertsPerDay": 1.53,
      "falseAlertsPer100PenDays": 20.44,
      "decision": "놓침을 줄이는 1차 선별. 단독 알림보다 관찰/추세 확인에 적합."
    },
    {
      "policy": "balanced",
      "label": "균형",
      "threshold": "30.4°C",
      "alerts": 90,
      "recall": 80,
      "precision": 35.6,
      "specificity": 92.1,
      "falseAlertsPerDay": 0.56,
      "falseAlertsPer100PenDays": 7.46,
      "decision": "F1 균형 후보. 환경 이상 기본 운영 기준으로 가장 현실적."
    },
    {
      "policy": "high_confidence",
      "label": "고확신",
      "threshold": "31.6°C",
      "alerts": 40,
      "recall": 47.5,
      "precision": 47.5,
      "specificity": 97.2,
      "falseAlertsPerDay": 0.2,
      "falseAlertsPer100PenDays": 2.7,
      "decision": "오탐을 줄인 고확신 기준. CCTV/현장 확인 우선순위에 적합."
    }
  ],
  "leadTime": {
    "events": 6,
    "matched": 3,
    "meanLeadHours": 23.1,
    "precisionProxy": 30.8,
    "recall24h": 50,
    "recall48h": 50,
    "recall72h": 50,
    "byEvent": [
      {
        "eventType": "environment_failure",
        "events": 1,
        "matched": 1,
        "recall24h": 100,
        "recall48h": 100,
        "recall72h": 100
      },
      {
        "eventType": "feed_drop",
        "events": 1,
        "matched": 0,
        "recall24h": 0,
        "recall48h": 0,
        "recall72h": 0
      },
      {
        "eventType": "fever",
        "events": 1,
        "matched": 1,
        "recall24h": 100,
        "recall48h": 100,
        "recall72h": 100
      },
      {
        "eventType": "respiratory",
        "events": 1,
        "matched": 1,
        "recall24h": 100,
        "recall48h": 100,
        "recall72h": 100
      },
      {
        "eventType": "treatment",
        "events": 1,
        "matched": 0,
        "recall24h": 0,
        "recall48h": 0,
        "recall72h": 0
      },
      {
        "eventType": "water_drop",
        "events": 1,
        "matched": 0,
        "recall24h": 0,
        "recall48h": 0,
        "recall72h": 0
      }
    ]
  },
  "clearfarmRecallCandidates": [
    {
      "id": "full_recall_candidate",
      "title": "전체 데이터 후보",
      "status": "관찰 민감도 후보",
      "configFile": "config/domain_rules_clearfarm_recall_candidate.json",
      "scope": "전체 기간",
      "changes": [
        "NH3 기준 29 -> 20",
        "CO2 기준 2984 -> 2500",
        "습도 75 이상 후보 추가"
      ],
      "threshold": "rule_score >= 0.3",
      "baselineAlerts": 739,
      "candidateAlerts": 867,
      "deltaAlerts": 128,
      "baselineRecall": 73.1,
      "candidateRecall": 88,
      "deltaRecall": 14.9,
      "baselinePrecision": 37.1,
      "candidatePrecision": 38.1,
      "deltaPrecision": 1,
      "baselineF1": 49.2,
      "candidateF1": 53.1,
      "deltaF1": 3.9,
      "reasonRows": [
        {
          "reason": "암모니아 농도 상승",
          "addedAlerts": 29,
          "hitRate": 44.8,
          "respiratoryRate": 31,
          "gutRate": 6.9,
          "heatRate": 10.3
        },
        {
          "reason": "암모니아 농도 상승",
          "addedAlerts": 29,
          "hitRate": 44.8,
          "respiratoryRate": 37.9,
          "gutRate": 0,
          "heatRate": 6.9
        },
        {
          "reason": "이산화탄소 농도 상승",
          "addedAlerts": 19,
          "hitRate": 36.8,
          "respiratoryRate": 15.8,
          "gutRate": 31.6,
          "heatRate": 0
        },
        {
          "reason": "이산화탄소 농도 상승 + 암모니아 농도 상승",
          "addedAlerts": 18,
          "hitRate": 55.6,
          "respiratoryRate": 44.4,
          "gutRate": 5.6,
          "heatRate": 5.6
        },
        {
          "reason": "이산화탄소 농도 상승 + 암모니아 농도 상승",
          "addedAlerts": 18,
          "hitRate": 33.3,
          "respiratoryRate": 22.2,
          "gutRate": 11.1,
          "heatRate": 0
        },
        {
          "reason": "이산화탄소 농도 상승",
          "addedAlerts": 13,
          "hitRate": 46.2,
          "respiratoryRate": 30.8,
          "gutRate": 15.4,
          "heatRate": 0
        }
      ],
      "interpretation": "전체 데이터에서는 민감도 개선 폭이 크지만 알림 수가 많이 늘어나므로 관찰 후보로만 둔다."
    },
    {
      "id": "jan_may_candidate",
      "title": "상반기 우선 후보",
      "status": "우선 추천",
      "configFile": "config/domain_rules_clearfarm_jan_may_candidate.json",
      "scope": "1~5월",
      "changes": [
        "NH3 기준 29 -> 20",
        "습도 75 이상 후보 추가",
        "CO2 후보 제외"
      ],
      "threshold": "rule_score >= 0.3",
      "baselineAlerts": 87,
      "candidateAlerts": 108,
      "deltaAlerts": 21,
      "baselineRecall": 42,
      "candidateRecall": 54,
      "deltaRecall": 12,
      "baselinePrecision": 24.1,
      "candidatePrecision": 25,
      "deltaPrecision": 0.9,
      "baselineF1": 30.7,
      "candidateF1": 34.2,
      "deltaF1": 3.5,
      "reasonRows": [
        {
          "reason": "humidity_high",
          "addedAlerts": 9,
          "hitRate": 22.2,
          "respiratoryRate": 22.2,
          "gutRate": 11.1,
          "heatRate": 0
        },
        {
          "reason": "암모니아 농도 상승",
          "addedAlerts": 6,
          "hitRate": 33.3,
          "respiratoryRate": 16.7,
          "gutRate": 16.7,
          "heatRate": 0
        },
        {
          "reason": "암모니아 농도 상승",
          "addedAlerts": 6,
          "hitRate": 33.3,
          "respiratoryRate": 16.7,
          "gutRate": 16.7,
          "heatRate": 0
        }
      ],
      "interpretation": "1~5월에서는 CO2를 제외한 NH3+습도 후보가 같은 민감도를 유지하면서 알림 부담을 조금 줄인다."
    },
    {
      "id": "precision_tuned_candidate",
      "title": "정밀도 필터 적용",
      "status": "다음 적용 후보",
      "configFile": "artifacts/clearfarm_precision_tuning/full_recall_candidate/clearfarm_precision_policy_metrics.csv",
      "scope": "전체 기간",
      "changes": [
        "기존 알림 유지",
        "새 후보 중 같은 원인 14일 내 반복 시 승격",
        "15건은 관찰 후보 유지"
      ],
      "threshold": "새 후보 중 같은 원인 14일 내 반복",
      "baselineAlerts": 739,
      "candidateAlerts": 852,
      "deltaAlerts": 113,
      "baselineRecall": 73.1,
      "candidateRecall": 87.2,
      "deltaRecall": 14.1,
      "baselinePrecision": 37.1,
      "candidatePrecision": 38.4,
      "deltaPrecision": 1.3,
      "baselineF1": 49.2,
      "candidateF1": 53.3,
      "deltaF1": 4.1,
      "suppressed": 15,
      "reasonRows": [
        {
          "reason": "암모니아 농도 상승",
          "addedAlerts": 29,
          "hitRate": 44.8,
          "respiratoryRate": 31,
          "gutRate": 6.9,
          "heatRate": 10.3
        },
        {
          "reason": "암모니아 농도 상승",
          "addedAlerts": 29,
          "hitRate": 44.8,
          "respiratoryRate": 37.9,
          "gutRate": 0,
          "heatRate": 6.9
        },
        {
          "reason": "이산화탄소 농도 상승",
          "addedAlerts": 19,
          "hitRate": 36.8,
          "respiratoryRate": 15.8,
          "gutRate": 31.6,
          "heatRate": 0
        },
        {
          "reason": "이산화탄소 농도 상승 + 암모니아 농도 상승",
          "addedAlerts": 18,
          "hitRate": 55.6,
          "respiratoryRate": 44.4,
          "gutRate": 5.6,
          "heatRate": 5.6
        },
        {
          "reason": "이산화탄소 농도 상승 + 암모니아 농도 상승",
          "addedAlerts": 18,
          "hitRate": 33.3,
          "respiratoryRate": 22.2,
          "gutRate": 11.1,
          "heatRate": 0
        },
        {
          "reason": "이산화탄소 농도 상승",
          "addedAlerts": 13,
          "hitRate": 46.2,
          "respiratoryRate": 30.8,
          "gutRate": 15.4,
          "heatRate": 0
        }
      ],
      "interpretation": "전체 recall 후보를 그대로 쓰지 않고 반복 신호만 승격해, 민감도 상승분을 대부분 유지하면서 알림 부담을 낮춘다."
    }
  ],
  "clearfarmRecallCandidate": {
    "id": "full_recall_candidate",
    "title": "전체 데이터 후보",
    "status": "관찰 민감도 후보",
    "configFile": "config/domain_rules_clearfarm_recall_candidate.json",
    "scope": "전체 기간",
    "changes": [
      "NH3 기준 29 -> 20",
      "CO2 기준 2984 -> 2500",
      "습도 75 이상 후보 추가"
    ],
    "threshold": "rule_score >= 0.3",
    "baselineAlerts": 739,
    "candidateAlerts": 867,
    "deltaAlerts": 128,
    "baselineRecall": 73.1,
    "candidateRecall": 88,
    "deltaRecall": 14.9,
    "baselinePrecision": 37.1,
    "candidatePrecision": 38.1,
    "deltaPrecision": 1,
    "baselineF1": 49.2,
    "candidateF1": 53.1,
    "deltaF1": 3.9,
    "reasonRows": [
      {
        "reason": "암모니아 농도 상승",
        "addedAlerts": 29,
        "hitRate": 44.8,
        "respiratoryRate": 31,
        "gutRate": 6.9,
        "heatRate": 10.3
      },
      {
        "reason": "암모니아 농도 상승",
        "addedAlerts": 29,
        "hitRate": 44.8,
        "respiratoryRate": 37.9,
        "gutRate": 0,
        "heatRate": 6.9
      },
      {
        "reason": "이산화탄소 농도 상승",
        "addedAlerts": 19,
        "hitRate": 36.8,
        "respiratoryRate": 15.8,
        "gutRate": 31.6,
        "heatRate": 0
      },
      {
        "reason": "이산화탄소 농도 상승 + 암모니아 농도 상승",
        "addedAlerts": 18,
        "hitRate": 55.6,
        "respiratoryRate": 44.4,
        "gutRate": 5.6,
        "heatRate": 5.6
      },
      {
        "reason": "이산화탄소 농도 상승 + 암모니아 농도 상승",
        "addedAlerts": 18,
        "hitRate": 33.3,
        "respiratoryRate": 22.2,
        "gutRate": 11.1,
        "heatRate": 0
      },
      {
        "reason": "이산화탄소 농도 상승",
        "addedAlerts": 13,
        "hitRate": 46.2,
        "respiratoryRate": 30.8,
        "gutRate": 15.4,
        "heatRate": 0
      }
    ],
    "interpretation": "전체 데이터에서는 민감도 개선 폭이 크지만 알림 수가 많이 늘어나므로 관찰 후보로만 둔다."
  },
  "managementCandidateCompare": {
    "sourceFile": "artifacts/management_rule_candidates/candidate_management_compare_summary.csv",
    "baseline": {
      "finalAlert": 26,
      "diseaseAlert": 20,
      "managementAlert": 0,
      "environmentAlert": 6
    },
    "candidate": {
      "finalAlert": 38,
      "diseaseAlert": 20,
      "managementAlert": 33,
      "environmentAlert": 6
    },
    "conclusion": "feed_drop min 후보 적용 시 사양관리 alert가 0건에서 33건으로 증가",
    "next": "급이 급락 신호는 살아났지만 전체 alert도 늘어나므로 실제 farm event log로 precision/recall을 검증한 뒤 production 승격 여부를 결정"
  },
  "externalChecks": [
    {
      "dataset": "HOTPIG",
      "role": "LSTM anomaly pipeline external sanity check",
      "result": "HS confirmed anomaly rate 11.8% vs TN validation 0.9% (12.6x)",
      "decision": "Use as evidence that the current anomaly pipeline reacts to physical heat-stress states."
    },
    {
      "dataset": "ASF Dryad challenge",
      "role": "ASF rule calibration and clinical-ground-truth evidence",
      "result": "rectal_temp_high 39.5C: sensitivity 48.7%, specificity 99.5%, precision 95.0%",
      "decision": "Keep rectal_temp_high as a high-precision rule, but combine it with anomaly score and other rules."
    },
    {
      "dataset": "Behavior x Heat Tolerance",
      "role": "Auxiliary physiology/feature-profile check",
      "result": "behavior_only HS confirmed anomaly rate 2.9%; behavior_muscle 100.0%; full 100.0%",
      "decision": "Use as auxiliary evidence only; temperature and muscle-temperature profiles explain the strong separation."
    }
  ],
  "weaknesses": [
    {
      "title": "고확신 알림의 누락 위험",
      "value": "26.1%",
      "label": "민감도",
      "detail": "rule_score >= 0.9에서는 정밀도 46.4%지만 민감도는 26.1%입니다. 알림 수는 줄지만 실제 이상을 많이 놓칠 수 있습니다.",
      "next": "운영 화면에서는 고확신 알림을 최종 판정이 아니라 CCTV 집중 확인 단계로 써야 합니다."
    },
    {
      "title": "사전 경보 포착 부족",
      "value": "50%",
      "label": "24시간 recall",
      "detail": "6개 이벤트 중 3개만 사전에 포착했습니다. 현재 lead-time 평가는 synthetic event 기준이라 실제 농장 기록으로 재검증이 필요합니다.",
      "next": "실제 farm event log를 쌓아 lead-time recall을 다시 계산해야 합니다."
    },
    {
      "title": "조기 선별의 오탐 부담",
      "value": "37.1%",
      "label": "정밀도",
      "detail": "rule_score >= 0.3은 민감도 73.1%로 넓게 잡지만 정밀도는 37.1%입니다.",
      "next": "확인 필요 큐에서 조치 결과를 누적해 threshold를 농장별로 보정해야 합니다."
    }
  ],
  "improvementPlan": [
    "고확신 알림은 최종 확정이 아니라 CCTV/현장 확인 우선순위로 표시",
    "실제 농장 이벤트 로그가 10건 이상 쌓이면 lead-time recall 재산출",
    "환경 온도 기준은 28.7/30.4/31.6°C 3단계로 나눠 운영 목적별로 표시",
    "상반기 전용 후보를 전체 후보와 나란히 비교해 우선 추천으로 관리",
    "ClearFarm 검증 결과를 반영해 절대 threshold를 농장별 상대 threshold로 전환"
  ],
  "notes": [
    "HOTPIG: HS confirmed anomaly rate 11.8% vs TN validation 0.9% (12.6x)",
    "현재 수치는 운영 전 검증용이며, 실제 농장 이벤트 리뷰가 쌓이면 threshold를 다시 조정해야 함"
  ]
};

export const CATEGORY_LABEL = { disease: "질병", management: "사양관리", environment: "환경", behavior: "행동" };
export const CATEGORY_ICON_NAME = { disease: "thermometer", management: "bowl", environment: "wind", behavior: "user" };

export const CHAMBER_BY_ID = Object.fromEntries(CHAMBERS.map((c) => [c.id, c]));

export function durationDays(startStr, endStr) {
  return Math.max(1, Math.round((new Date(endStr) - new Date(startStr)) / 86400000));
}
