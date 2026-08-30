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

CATEGORY_LABEL = {"disease": "질병", "management": "사양관리", "environment": "환경", "behavior": "행동"}
CATEGORY_ICON_NAME = {"disease": "thermometer", "management": "bowl", "environment": "wind", "behavior": "user"}

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
            }
        )

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

    present = {c["buildingLabel"] for c in chambers} | {r["buildingLabel"] for r in no_data_rooms}
    buildings = [label for label in BUILDING_ORDER if label in present]
    for chamber in chambers:
        if chamber["buildingLabel"] not in buildings:
            buildings.append(chamber["buildingLabel"])

    return {
        "chambers": chambers,
        "noDataRooms": no_data_rooms,
        "buildings": buildings,
        "totalRooms": len(chambers) + len(no_data_rooms),
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
            }
        )
    return incidents
