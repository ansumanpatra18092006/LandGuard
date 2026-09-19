import pytest

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from sqlalchemy.exc import OperationalError


@pytest.fixture
def observations(client, payload):
    rows = [
        payload,
        {**payload, "project_id": "TEST02", "compensation_completion_pct": 75,
         "possession_pct": 90, "legal_disputes": 0, "pending_approvals": 0,
         "stakeholder_response_days": 31, "acquisition_stage": "POSSESSION"},
        {**payload, "project_id": "TEST03", "district": "Nagpur", "compensation_completion_pct": 50,
         "possession_pct": 50, "legal_disputes": 5, "pending_approvals": 2,
         "stakeholder_response_days": 10, "project_type": "RAILWAY"},
    ]
    for row in rows:
        assert client.post("/api/v1/projects", json=row).status_code == 201


def test_summary(client, observations):
    result = client.get("/api/v1/dashboard/summary").json()
    assert result["total_projects"] == 3
    assert result["pending_approvals"] == 5
    assert result["projects_with_legal_disputes"] == 2
    assert result["avg_compensation_pct"] == 50
    assert result["illustrative_projects"] == 0
    assert result["user_entered_projects"] == 3
    assert result["high_risk"] is None and result["medium_risk"] is None and result["low_risk"] is None


def test_district_summaries_remain_separate(client, observations):
    rows = client.get("/api/v1/dashboard/district-summary").json()
    assert len(rows) == 2
    assert {row["district"]: row["project_count"] for row in rows} == {"Nagpur": 1, "Pune": 2}
    pune = next(row for row in rows if row["district"] == "Pune")
    assert pune == dict(state="Maharashtra", district="Pune", project_count=2,
                        avg_compensation_pct=50, avg_possession_pct=50, pending_approvals=3, legal_disputes=1,
                        projects_with_pending_approvals=1, projects_with_legal_disputes=1)


def test_stages(client, observations):
    assert client.get("/api/v1/dashboard/stage-distribution").json() == [
        {"stage": "POSSESSION", "count": 1}, {"stage": "SURVEY", "count": 2}]


def test_operational_threshold_boundaries(client, observations, monkeypatch):
    monkeypatch.setattr(settings, "compensation_threshold_pct", 50)
    monkeypatch.setattr(settings, "possession_threshold_pct", 50)
    monkeypatch.setattr(settings, "slow_response_days", 30)
    result = client.get("/api/v1/dashboard/operational-risks").json()
    assert result["projects_with_legal_disputes"] == 2
    assert result["projects_with_pending_approvals"] == 2
    assert result["projects_below_compensation_threshold"] == 1
    assert result["projects_below_possession_threshold"] == 1
    assert result["projects_with_slow_stakeholder_response"] == 1
    monkeypatch.setattr(settings, "compensation_threshold_pct", 76)
    assert client.get("/api/v1/dashboard/operational-risks").json()["projects_below_compensation_threshold"] == 3


@pytest.mark.parametrize("query,count", [
    ("state=Maharashtra", 3), ("district=Pune", 2), ("project_type=RAILWAY", 1),
    ("acquisition_stage=POSSESSION", 1), ("search=TEST02", 1),
    ("state=Maharashtra&acquisition_stage=SURVEY", 2), ("search=%25", 0),
])
def test_shared_filters(client, observations, query, count):
    assert client.get(f"/api/v1/projects?{query}&page_size=1").json()["total"] == count
    assert client.get(f"/api/v1/dashboard/summary?{query}").json()["total_projects"] == count
    districts = client.get(f"/api/v1/dashboard/district-summary?{query}").json()
    stages = client.get(f"/api/v1/dashboard/stage-distribution?{query}").json()
    assert sum(row["project_count"] for row in districts) == count
    assert sum(row["count"] for row in stages) == count


def test_empty(client):
    result = client.get("/api/v1/dashboard/summary").json()
    assert result["total_projects"] == 0 and result["avg_compensation_pct"] is None
    assert client.get("/api/v1/dashboard/district-summary").json() == []
    assert client.get("/api/v1/dashboard/stage-distribution").json() == []
    result = client.get("/api/v1/dashboard/operational-risks").json()
    assert all(value == 0 for key, value in result.items() if key.startswith("projects_"))


def test_analytics_after_update_and_delete(client, observations, payload):
    client.put("/api/v1/projects/TEST01", json={**payload, "pending_approvals": 0})
    assert client.get("/api/v1/dashboard/summary").json()["pending_approvals"] == 2
    client.delete("/api/v1/projects/TEST03")
    assert client.get("/api/v1/dashboard/summary").json()["pending_approvals"] == 0


def test_sanitized_database_error(client):
    def fail():
        raise OperationalError("sensitive SQL", {}, Exception("private connection information"))
    app.dependency_overrides[get_db] = fail
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 503
    assert "private" not in response.text and "sensitive" not in response.text


def test_invalid_filter(client):
    assert client.get("/api/v1/dashboard/summary?project_type=INVALID").status_code == 422
