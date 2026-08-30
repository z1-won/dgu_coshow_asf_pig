"""FastAPI backend for the operator dashboard.

Step 3 of the backend build-out (see docs/00_overview/NEXT_STEPS.md): a
review POST endpoint backed by ``pigproject.incident_review``, so a
confirm/dismiss click can persist straight to
``data/processed/incident_review_log.csv`` instead of only living in the
browser's localStorage (or needing the CSV export/import bridge). Step 2's
GET endpoints (chambers/incidents/categories) read the same artifacts/*.csv
the dashboard's build-time generator does, via pigproject.dashboard_data --
see tests/test_dashboard_data.py for the parity check against the .mjs
output. The dashboard's own switch from static import to fetch comes next.

Run locally with:

    pip install -e ".[api]"
    pig-serve-api
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pigproject.dashboard_data import (
    CATEGORY_ICON_NAME,
    CATEGORY_LABEL,
    DEFAULT_CHAMBER_SUMMARY_CSV,
    DEFAULT_INCIDENT_QUEUE_CSV,
    load_chambers,
    load_incidents,
)
from pigproject.incident_review import (
    append_summary_history,
    apply_single_review,
    load_or_bootstrap_review_log,
    summarize_review_log,
    write_review_log,
)

REVIEW_LOG_CSV = "data/processed/incident_review_log.csv"
SUMMARY_HISTORY_CSV = "data/processed/incident_review_summary_history.csv"
VALID_DECISIONS = {"confirmed", "dismissed"}

app = FastAPI(title="PigProject API", version="0.1.0")

# Vite's dev server default port. Widen this (or read from an env var) once
# the dashboard is actually deployed somewhere other than localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/chambers")
def get_chambers() -> dict:
    try:
        return load_chambers(DEFAULT_CHAMBER_SUMMARY_CSV)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"pipeline output not found: {exc.filename}") from exc


@app.get("/api/incidents")
def get_incidents() -> dict:
    try:
        incidents = load_incidents(DEFAULT_INCIDENT_QUEUE_CSV)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"pipeline output not found: {exc.filename}") from exc
    return {"incidents": incidents}


@app.get("/api/categories")
def get_categories() -> dict:
    return {"categoryLabel": CATEGORY_LABEL, "categoryIconName": CATEGORY_ICON_NAME}


class ReviewRequest(BaseModel):
    decision: str
    reviewed_by: str | None = None


@app.post("/api/incidents/{incident_id}/review")
def post_incident_review(incident_id: str, body: ReviewRequest) -> dict:
    if body.decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {sorted(VALID_DECISIONS)}")

    try:
        review_log = load_or_bootstrap_review_log(REVIEW_LOG_CSV, DEFAULT_INCIDENT_QUEUE_CSV)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"pipeline output not found: {exc.filename}") from exc

    try:
        updated = apply_single_review(review_log, incident_id, body.decision, reviewed_by=body.reviewed_by)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"incident_id not found: {incident_id}") from None

    write_review_log(updated, REVIEW_LOG_CSV)
    summary = summarize_review_log(updated)
    append_summary_history(summary, SUMMARY_HISTORY_CSV)

    row = updated.set_index("incident_id").loc[incident_id]
    return {
        "incident_id": incident_id,
        "review_status": row["review_status"],
        "confirmed": bool(row["confirmed"]) if row["confirmed"] in (True, False) else None,
        "false_alarm": bool(row["false_alarm"]) if row["false_alarm"] in (True, False) else None,
        "resolved_at": row["resolved_at"],
        "reviewed_by": row["reviewed_by"],
    }


def main() -> None:
    import uvicorn

    uvicorn.run("pigproject.api:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
