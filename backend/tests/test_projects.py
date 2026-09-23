import pytest
from sqlalchemy import select
from app.models.project import Project


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["model_status"] in {"not_loaded", "available"}


def test_crud_persists_across_sessions(client, database, payload):
    created = client.post("/api/v1/projects", json=payload)
    assert created.status_code == 201
    assert created.json()["data_source"] == "USER_ENTERED"
    with database() as db:
        assert db.scalar(select(Project)).project_id == "TEST01"
    assert client.get("/api/v1/projects/TEST01").json()["project_name"] == payload["project_name"]
    payload["compensation_completion_pct"] = 80
    assert client.put("/api/v1/projects/TEST01", json=payload).json()["compensation_completion_pct"] == 80
    assert client.delete("/api/v1/projects/TEST01").status_code == 204
    assert client.get("/api/v1/projects/TEST01").status_code == 404


def test_duplicate_and_missing(client, payload):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    assert client.post("/api/v1/projects", json=payload).status_code == 409
    assert client.put("/api/v1/projects/missing", json=payload).status_code == 404
    assert client.delete("/api/v1/projects/missing").status_code == 404
    assert client.get("/api/v1/projects").json()["total"] == 1


@pytest.mark.parametrize("field,value", [
    ("compensation_completion_pct", 101), ("possession_pct", -1),
    ("rehabilitation_completion_pct", 101), ("latitude", 91), ("longitude", -181),
    ("land_area", -1), ("pending_approvals", -1), ("legal_disputes", -2),
    ("affected_families", -1), ("stakeholder_response_days", -1),
    ("elapsed_acquisition_days", -1), ("project_id", " "),
    ("project_name", " "), ("state", " "), ("project_type", "INVALID"),
    ("acquisition_stage", "INVALID"), ("affected_families", 1.5),
])
def test_validation(client, payload, field, value):
    payload[field] = value
    assert client.post("/api/v1/projects", json=payload).status_code == 422
    assert client.get("/api/v1/projects").json()["total"] == 0


def test_filter_pagination(client, payload):
    client.post("/api/v1/projects", json=payload)
    client.post("/api/v1/projects", json={**payload, "project_id": "TEST02", "district": "Nashik"})
    assert client.get("/api/v1/projects?district=Pune").json()["total"] == 1
    assert client.get("/api/v1/projects?search=test02").json()["total"] == 1
    assert client.get("/api/v1/projects?search=%25").json()["total"] == 0
    page = client.get("/api/v1/projects?page=2&page_size=1").json()
    assert page["total"] == 2 and page["items"][0]["project_id"] == "TEST02"
    assert client.get("/api/v1/projects?page=0").status_code == 422


def test_sort_projects(client, payload):
    client.post("/api/v1/projects", json=payload)
    client.post("/api/v1/projects", json={**payload, "project_id": "TEST02", "district": "Nashik", "pending_approvals": 1})
    asc = client.get("/api/v1/projects?sort_by=district&sort_dir=asc").json()["items"]
    assert [item["project_id"] for item in asc] == ["TEST02", "TEST01"]
    desc = client.get("/api/v1/projects?sort_by=district&sort_dir=desc").json()["items"]
    assert [item["project_id"] for item in desc] == ["TEST01", "TEST02"]
    assert client.get("/api/v1/projects?sort_by=not_a_field").status_code == 422


def test_seed_idempotent(database, monkeypatch):
    from app.db import seed
    monkeypatch.setattr(seed, "SessionLocal", database)
    seed.main()
    seed.main()
    with database() as db:
        rows = db.scalars(select(Project)).all()
        assert len(rows) == len(seed.SEEDS)
        assert all(row.data_source == "ILLUSTRATIVE" for row in rows)


def test_project_history_persists_field_changes(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    updated = {**payload, 'compensation_completion_pct': 72, 'pending_approvals': 1}
    assert client.put('/api/v1/projects/TEST01', json=updated).status_code == 200
    history = client.get('/api/v1/projects/TEST01/history')
    assert history.status_code == 200
    data = history.json()
    assert len(data['snapshots']) >= 2
    events = [row for row in data['events'] if row['event_type'] == 'PROJECT_UPDATED']
    assert events
    assert 'compensation_completion_pct' in events[0]['changed_fields']
    assert 'pending_approvals' in events[0]['changed_fields']


def test_dashboard_delay_trends_follow_project_snapshots(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    assert client.put('/api/v1/projects/TEST01', json={**payload, 'legal_disputes': 2}).status_code == 200
    response = client.get('/api/v1/dashboard/delay-trends?group_by=district&days=365')
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row['group_label'] == 'Pune, Maharashtra' for row in rows)
    assert all(0 <= row['avg_acquisition_risk_score'] <= 100 for row in rows)
