// Thin client for the FastAPI backend (src/pigproject/api.py). Every call can
// fail (backend not running, CORS, network) -- callers are expected to catch
// and fall back to the static build-time snapshot (see DashboardDataContext.jsx).

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json();
}

export function fetchChambers() {
  return getJson("/api/chambers");
}

export function fetchIncidents() {
  return getJson("/api/incidents");
}

export function fetchCategories() {
  return getJson("/api/categories");
}

export async function postReview(incidentId, decision, reviewedBy) {
  const res = await fetch(`${API_BASE}/api/incidents/${encodeURIComponent(incidentId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, reviewed_by: reviewedBy || null }),
  });
  if (!res.ok) throw new Error(`POST review -> ${res.status}`);
  return res.json();
}
