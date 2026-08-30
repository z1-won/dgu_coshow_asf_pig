import pandas as pd
from fastapi.testclient import TestClient

from pigproject.api import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_chambers_returns_real_pipeline_output():
    response = client.get("/api/chambers")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"chambers", "noDataRooms", "buildings", "totalRooms"}
    assert body["totalRooms"] == len(body["chambers"]) + len(body["noDataRooms"])
    assert body["buildings"]  # non-empty on the real dataset
    chamber = body["chambers"][0]
    assert set(chamber.keys()) == {"id", "buildingLabel", "code", "room", "track", "windows", "mean", "max", "modelTier", "lowConf"}


def test_get_incidents_returns_real_pipeline_output():
    response = client.get("/api/incidents")

    assert response.status_code == 200
    body = response.json()
    assert "incidents" in body
    if body["incidents"]:
        incident = body["incidents"][0]
        assert set(incident.keys()) == {"id", "chamberId", "category", "start", "end", "windows", "score", "reasonParts", "action"}


def test_get_categories_returns_label_and_icon_maps():
    response = client.get("/api/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["categoryLabel"]["disease"] == "질병"
    assert body["categoryIconName"]["disease"] == "thermometer"


def test_post_review_confirms_a_real_incident_and_persists(tmp_path, monkeypatch):
    import pigproject.api as api_module

    review_log_path = tmp_path / "incident_review_log.csv"
    history_path = tmp_path / "incident_review_summary_history.csv"
    monkeypatch.setattr(api_module, "REVIEW_LOG_CSV", str(review_log_path))
    monkeypatch.setattr(api_module, "SUMMARY_HISTORY_CSV", str(history_path))

    response = client.post("/api/incidents/disease-0001/review", json={"decision": "confirmed", "reviewed_by": "test_op"})

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == "disease-0001"
    assert body["review_status"] == "confirmed"
    assert body["confirmed"] is True
    assert body["reviewed_by"] == "test_op"
    assert review_log_path.exists()
    assert history_path.exists()

    # persisted -- a second request against the same paths sees the prior decision
    review_log = pd.read_csv(review_log_path)
    assert review_log.set_index("incident_id").loc["disease-0001", "review_status"] == "confirmed"


def test_post_review_rejects_unknown_decision(tmp_path, monkeypatch):
    import pigproject.api as api_module

    monkeypatch.setattr(api_module, "REVIEW_LOG_CSV", str(tmp_path / "incident_review_log.csv"))
    monkeypatch.setattr(api_module, "SUMMARY_HISTORY_CSV", str(tmp_path / "incident_review_summary_history.csv"))

    response = client.post("/api/incidents/disease-0001/review", json={"decision": "maybe"})

    assert response.status_code == 400


def test_post_review_404s_for_unknown_incident(tmp_path, monkeypatch):
    import pigproject.api as api_module

    monkeypatch.setattr(api_module, "REVIEW_LOG_CSV", str(tmp_path / "incident_review_log.csv"))
    monkeypatch.setattr(api_module, "SUMMARY_HISTORY_CSV", str(tmp_path / "incident_review_summary_history.csv"))

    response = client.post("/api/incidents/does-not-exist/review", json={"decision": "confirmed"})

    assert response.status_code == 404
