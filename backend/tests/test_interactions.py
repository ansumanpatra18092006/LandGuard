import pytest

from app.core.config import settings


@pytest.fixture
def records(client, payload):
    for row in [payload, {**payload, "project_id": "TEST02", "pending_approvals": 0, "legal_disputes": 0,
                         "compensation_completion_pct": 80, "possession_pct": 90, "stakeholder_response_days": 50},
                {**payload, "project_id": "TEST03", "district": "Nashik", "compensation_completion_pct": 50,
                 "possession_pct": 50, "pending_approvals": 1, "legal_disputes": 0}]:
        assert client.post("/api/v1/projects", json=row).status_code == 201


@pytest.mark.parametrize("indicator,ids", [
    ("pending_approvals", ["TEST01", "TEST03"]), ("legal_disputes", ["TEST01"]),
    ("compensation_lag", ["TEST01"]), ("possession_lag", ["TEST01"]), ("slow_response", ["TEST02"]),
])
def test_drilldown_counts_match_rows(client, records, indicator, ids, monkeypatch):
    monkeypatch.setattr(settings, "compensation_threshold_pct", 50)
    monkeypatch.setattr(settings, "possession_threshold_pct", 50)
    monkeypatch.setattr(settings, "slow_response_days", 30)
    query = f"indicator={indicator}"
    page = client.get(f"/api/v1/projects?{query}").json()
    assert [p["project_id"] for p in page["items"]] == ids
    assert client.get(f"/api/v1/dashboard/summary?{query}").json()["total_projects"] == len(ids)
    assert sum(row["count"] for row in client.get(f"/api/v1/dashboard/stage-distribution?{query}").json()) == len(ids)


def test_combined_filters_and_validation(client, records):
    assert client.get("/api/v1/projects?indicator=pending_approvals&district=Pune").json()["total"] == 1
    assert client.get("/api/v1/projects?indicator=made_up").status_code == 422
    assert client.get("/api/v1/dashboard/summary?indicator=made_up").status_code == 422


def test_notices_are_current_record_observations(client, records, payload):
    data = client.get("/api/v1/review-notices?limit=1").json()
    assert data["total"] == 2 and len(data["items"]) == 1
    assert "updated_at" in data["items"][0]
    assert "severity" not in data["items"][0]  # no invented risk/severity
    client.put("/api/v1/projects/TEST01", json={**payload, "pending_approvals": 0, "legal_disputes": 0})
    assert client.get("/api/v1/review-notices").json()["total"] == 1
    assert client.get("/api/v1/review-notices?limit=0").status_code == 422
