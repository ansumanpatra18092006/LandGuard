import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.security import current_user

TEST_USER = {"id": "00000000-0000-4000-8000-000000000001", "email": "test@example.org",
             "display_name": "Test State Officer", "role": "STATE_OFFICER", "status": "active",
             "state": "Maharashtra", "district": None, "project_ids": []}


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture
def client(database):
    def override():
        with database() as db:
            yield db
    app.dependency_overrides[get_db] = override
    app.dependency_overrides[current_user] = lambda: dict(TEST_USER)
    try:
        with TestClient(app) as test_client:
            test_client.headers.update({"X-LandGuard-Request": "1"})
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def payload():
    return dict(project_id="TEST01", project_name="Fictional test project", project_type="ROAD",
                state="Maharashtra", district="Pune", latitude=18.52, longitude=73.85,
                land_area=100, affected_families=50, compensation_completion_pct=25,
                pending_approvals=3, legal_disputes=1, possession_pct=10,
                rehabilitation_completion_pct=20, stakeholder_response_days=30,
                elapsed_acquisition_days=180, acquisition_stage="SURVEY",
                original_cost_crore=420, expenditure_crore=155, original_end_date="2027-03-31")
