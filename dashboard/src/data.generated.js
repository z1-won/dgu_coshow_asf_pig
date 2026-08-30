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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": true
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
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
    "lowConf": false
  }
];

export const NO_DATA_ROOMS = [
  {
    "id": "bioenergy:71408:3-nodata",
    "buildingLabel": "1동",
    "code": "bioenergy:71408:3",
    "room": "3번 돈방",
    "note": "관측 횟수 부족(19회, 최소 24회 필요)으로 분석 대상에서 제외됨",
    "isNoData": true
  }
];

export const BUILDINGS = [
  "1동",
  "2동",
  "3동"
];
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
    "action": "체온 상승 개체 확인, 증상 관찰, 격리 필요성 판단, 수의사 확인"
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
    "action": "체온 상승 개체 확인, 증상 관찰, 격리 필요성 판단, 수의사 확인"
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
    "action": "환기량 증대, CO2/NH3 센서 재확인, 분뇨/환기 설비 점검"
  }
];

export const CATEGORY_LABEL = { disease: "질병", management: "사양관리", environment: "환경", behavior: "행동" };
export const CATEGORY_ICON_NAME = { disease: "thermometer", management: "bowl", environment: "wind", behavior: "user" };

export const CHAMBER_BY_ID = Object.fromEntries(CHAMBERS.map((c) => [c.id, c]));

export function durationDays(startStr, endStr) {
  return Math.max(1, Math.round((new Date(endStr) - new Date(startStr)) / 86400000));
}
