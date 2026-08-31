"""Load and shape real pipeline outputs into the JSON structure the operator
dashboard expects (chambers, incidents, buildings, categories).

This is a Python port of ``dashboard/scripts/generate-dashboard-data.mjs`` --
the transformation rules (building labels, room names, reason-code -> Korean
label mapping, incident score selection) must stay in sync with that file.
It exists so the FastAPI backend can serve the same shape live instead of
only being available as the dashboard's build-time static generator.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DEFAULT_CHAMBER_SUMMARY_CSV = "artifacts/final_chamber_summary.csv"
DEFAULT_INCIDENT_QUEUE_CSV = "artifacts/action_queues/incident_queue.csv"

CHAMBER_SOURCE_CSV = "artifacts/final_chamber_summary.csv"
INCIDENT_SOURCE_CSV = "artifacts/action_queues/incident_queue.csv"

CATEGORY_LABEL = {"disease": "질병", "management": "사양관리", "environment": "환경", "behavior": "행동"}
CATEGORY_ICON_NAME = {"disease": "thermometer", "management": "bowl", "environment": "wind", "behavior": "user"}
FARM_SCOPE = {
    "farmId": "demo-farm",
    "farmName": "시연 농장",
    "mode": "single_farm",
    "description": "운영 제품에서는 로그인한 농장의 돈사/돈방만 표시",
}

TRACK_LABEL = {"bioenergy": "체온·환경 센서", "activity_622": "카메라 행동분석"}

REASON_TOKEN_LABELS = [
    ("rectal_temp_high", "체온 상승"),
    ("co2_high", "이산화탄소 농도 상승"),
    ("nh3_high", "암모니아 농도 상승"),
    ("feed_drop", "사료섭취 감소"),
    ("feed_spike", "사료섭취 급증"),
    ("water_drop", "급수량 감소"),
    ("water_spike", "급수량 급증"),
    ("treatment", "치료 이력 확인"),
    ("environment_failure", "환경 설비 이상"),
    ("ventilation", "환기 이상"),
]

BUILDING_ORDER = ["1동", "2동", "3동"]
BIOENERGY_BUILDING_BY_SOURCE = {"71408": "1동", "71763": "2동"}

_BIOENERGY_RE = re.compile(r"^bioenergy:([^:]+):(\d+)$")
_ACTIVITY_RE = re.compile(r"^activity622:facility(\d+):pen(\d+)$")


def _as_number(value: object, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return fallback if parsed != parsed else parsed  # NaN check


def _round(value: object, digits: int = 4) -> float:
    return round(_as_number(value), digits)


def building_label(track: str, source_dataset: str) -> str:
    if track == "bioenergy":
        return BIOENERGY_BUILDING_BY_SOURCE.get(str(source_dataset), f"{source_dataset}동")
    if track == "activity_622":
        return "3동"
    return str(source_dataset) if source_dataset else "기타"


def chamber_room(chamber_id: str) -> str:
    bioenergy_match = _BIOENERGY_RE.match(chamber_id)
    if bioenergy_match:
        return f"{bioenergy_match.group(2)}번 돈방"
    activity_match = _ACTIVITY_RE.match(chamber_id)
    if activity_match:
        return f"{activity_match.group(1)}구역 {activity_match.group(2)}번방"
    return chamber_id


def track_label(track: str) -> str:
    return TRACK_LABEL.get(track, track)


def reason_parts(reason: str) -> list[str]:
    reason = reason or ""
    found: list[str] = []
    for token, label in REASON_TOKEN_LABELS:
        if token in reason and label not in found:
            found.append(label)
    if found:
        return found
    stripped = re.sub(r"^rule:\s*", "", reason)
    return [part.strip() for part in re.split(r"[|,]", stripped) if part.strip()]


def incident_score(row: pd.Series) -> float:
    by_queue = {
        "disease": _as_number(row.get("max_track_score")),
        "management": _as_number(row.get("max_management_score")),
        "environment": _as_number(row.get("max_environment_score")),
    }
    queue = row.get("queue")
    if queue in by_queue:
        return _round(by_queue[queue])
    return _round(max(by_queue.values(), default=0.0))


def score_field_for_queue(queue: str) -> str:
    return {
        "disease": "max_track_score",
        "management": "max_management_score",
        "environment": "max_environment_score",
    }.get(queue, "max(track, management, environment)")


def category_evidence_label(queue: str) -> str:
    return {
        "disease": "질병 큐: 체온·행동 이상 점수 우선",
        "management": "사양관리 큐: 급이·급수 점수 우선",
        "environment": "환경 큐: CO2/NH3/환기 점수 우선",
    }.get(queue, "복합 큐: 가장 높은 이상 점수 사용")


def operational_stage_from_scores(track_score: float, management_score: float, environment_score: float) -> dict:
    if track_score >= 0.9 or environment_score >= 0.9:
        return {
            "key": "cctv_focus",
            "label": "CCTV 확인",
            "priorityLabel": "CCTV 확인",
            "description": "고확신 이상 또는 환경 점수 상승",
        }
    if track_score >= 0.6 or environment_score >= 0.6 or management_score >= 0.6:
        return {
            "key": "caution",
            "label": "확인 필요",
            "priorityLabel": "확인 필요",
            "description": "담당자 점검 순번 상향",
        }
    return {
        "key": "observe",
        "label": "관찰 후보",
        "priorityLabel": "관찰",
        "description": "다음 관측에서 반복 여부 확인",
    }


def operational_stage_from_chamber(chamber: dict, incident: dict | None) -> dict:
    if chamber.get("isNoData"):
        return {"key": "nodata", "label": "데이터 부족", "description": "수집 기준 미달"}
    if incident and incident.get("operationalStage"):
        return incident["operationalStage"]
    if chamber.get("modelTier") in {"medium", "high"}:
        return {"key": "observe", "label": "관찰 후보", "description": "모델 관심 구간"}
    return {"key": "normal", "label": "정상", "description": "확인 필요 이벤트 없음"}


def attach_barn_comparison(chambers: list[dict]) -> None:
    by_building: dict[str, list[dict]] = {}
    for chamber in chambers:
        by_building.setdefault(str(chamber.get("buildingLabel", "")), []).append(chamber)

    for building_items in by_building.values():
        comparable = [item for item in building_items if isinstance(item.get("max"), (int, float))]
        if not comparable:
            continue
        mean_max = sum(float(item["max"]) for item in comparable) / len(comparable)
        ranked = sorted(comparable, key=lambda item: float(item["max"]), reverse=True)
        for item in comparable:
            item["barnComparison"] = {
                "scope": item["buildingLabel"],
                "comparedPens": len(comparable),
                "meanMaxScore": _round(mean_max),
                "deltaFromBarnMean": _round(float(item["max"]) - mean_max),
                "maxScoreRank": ranked.index(item) + 1,
            }


def date_only(value: object) -> str:
    text = str(value) if value not in (None, "") else ""
    return text.split(" ")[0] if text else text


def load_chambers(chamber_summary_csv: str | Path = DEFAULT_CHAMBER_SUMMARY_CSV) -> dict:
    """Return {chambers, noDataRooms, buildings, totalRooms} -- the same shape
    generate-dashboard-data.mjs writes as CHAMBERS/NO_DATA_ROOMS/BUILDINGS/TOTAL_ROOMS."""
    df = pd.read_csv(chamber_summary_csv, low_memory=False)
    chambers = []
    for _, row in df.iterrows():
        chamber_id = str(row["chamber_id"])
        chambers.append(
            {
                "id": chamber_id,
                "buildingLabel": building_label(str(row.get("track", "")), str(row.get("source_dataset", ""))),
                "code": chamber_id,
                "room": chamber_room(chamber_id),
                "track": track_label(str(row.get("track", ""))),
                "windows": int(_as_number(row.get("windows"))),
                "mean": _round(row.get("mean_score")),
                "max": _round(row.get("max_score")),
                "modelTier": row.get("chamber_tier") or "unknown",
                "lowConf": str(row.get("low_confidence")).strip().lower() == "true",
                "evidence": {
                    "sourceCsv": CHAMBER_SOURCE_CSV,
                    "sourceDataset": str(row.get("source_dataset", "")),
                    "scoreFields": ["mean_score", "max_score", "chamber_tier", "operational_alert_windows"],
                    "scoreMeaning": "평소 패턴 대비 돈방별 이상 점수 요약",
                    "statusRule": "operationalStage 기준: 알림 큐가 있으면 확인/CCTV 단계, 없지만 모델 tier가 medium/high면 관찰 후보",
                },
            }
        )
        chambers[-1]["operationalStage"] = operational_stage_from_chamber(chambers[-1], None)
    attach_barn_comparison(chambers)

    no_data_rooms = []
    if not any(c["id"] == "bioenergy:71408:3" for c in chambers):
        no_data_rooms.append(
            {
                "id": "bioenergy:71408:3-nodata",
                "buildingLabel": "1동",
                "code": "bioenergy:71408:3",
                "room": "3번 돈방",
                "note": "관측 횟수 부족(19회, 최소 24회 필요)으로 분석 대상에서 제외됨",
                "isNoData": True,
            }
        )
        no_data_rooms[-1]["operationalStage"] = operational_stage_from_chamber(no_data_rooms[-1], None)

    present = {c["buildingLabel"] for c in chambers} | {r["buildingLabel"] for r in no_data_rooms}
    buildings = [label for label in BUILDING_ORDER if label in present]
    for chamber in chambers:
        if chamber["buildingLabel"] not in buildings:
            buildings.append(chamber["buildingLabel"])

    return {
        "chambers": chambers,
        "noDataRooms": no_data_rooms,
        "buildings": buildings,
        "farmScope": FARM_SCOPE,
        "totalRooms": len(chambers) + len(no_data_rooms),
    }


def environment_temp_stage(row: pd.Series) -> dict:
    return {
        "policy": str(row.get("environment_temp_policy", "") or ""),
        "label": str(row.get("environment_temp_label", "") or ""),
        "action": str(row.get("environment_temp_action", "") or ""),
    }


def load_incidents(incident_queue_csv: str | Path = DEFAULT_INCIDENT_QUEUE_CSV) -> list[dict]:
    """Return the INCIDENTS list shape."""
    df = pd.read_csv(incident_queue_csv, low_memory=False)
    incidents = []
    for _, row in df.iterrows():
        incidents.append(
            {
                "id": row["incident_id"],
                "chamberId": row["chamber_id"],
                "category": row["queue"],
                "start": date_only(row.get("incident_start_datetime")),
                "end": date_only(row.get("incident_end_datetime")),
                "windows": int(_as_number(row.get("window_count"))),
                "score": incident_score(row),
                "reasonParts": reason_parts(str(row.get("reason", ""))),
                "action": row.get("recommended_action") or "현장 확인 후 조치 결과를 기록",
                "operationalStage": operational_stage_from_scores(
                    _as_number(row.get("max_track_score")),
                    _as_number(row.get("max_management_score")),
                    _as_number(row.get("max_environment_score")),
                ),
                "environmentTemp": environment_temp_stage(row),
                "evidence": {
                    "sourceCsv": INCIDENT_SOURCE_CSV,
                    "rawReason": str(row.get("reason", "")),
                    "scoreField": score_field_for_queue(str(row.get("queue", ""))),
                    "scoreFormula": category_evidence_label(str(row.get("queue", ""))),
                    "inputScores": {
                        "track": _round(row.get("max_track_score")),
                        "management": _round(row.get("max_management_score")),
                        "environment": _round(row.get("max_environment_score")),
                    },
                    "decisionRule": "domain rule이 감지한 이벤트를 action queue로 승격",
                },
            }
        )
    return incidents


def attach_operational_stages(chambers: list[dict], no_data_rooms: list[dict], incidents: list[dict]) -> None:
    incidents_by_chamber = {incident["chamberId"]: incident for incident in incidents}
    for chamber in chambers:
        chamber["operationalStage"] = operational_stage_from_chamber(chamber, incidents_by_chamber.get(chamber["id"]))
    for room in no_data_rooms:
        room["operationalStage"] = operational_stage_from_chamber(room, None)
