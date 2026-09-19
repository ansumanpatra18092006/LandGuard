"""Opt-in runtime verification in an isolated, temporary PostgreSQL schema."""
import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.config import BACKEND_DIR, settings
from app.db import seed
from app.db.session import get_db
from app.main import app
from app.core.security import current_user


def verify_postgres(url: str) -> dict:
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    if engine.dialect.name != "postgresql":
        raise ValueError("A PostgreSQL URL is required")
    schema = "landguard_verify_" + uuid4().hex
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.commit()
            original_factory = seed.SessionLocal
            original_overrides = app.dependency_overrides.copy()
            try:
                connection.execute(text(f'SET search_path TO "{schema}", public'))
                connection.commit()
                config = Config(str(BACKEND_DIR / "alembic.ini"))
                config.attributes["connection"] = connection
                # Never pick up an existing public.alembic_version through search_path.
                config.attributes["version_table_schema"] = schema
                command.upgrade(config, "head")
                version = connection.scalar(text("SELECT PostGIS_Version()"))
                factory = sessionmaker(bind=connection, expire_on_commit=False,
                                       join_transaction_mode="create_savepoint")
                seed.SessionLocal = factory
                seed.main()
                seed.main()

                def database():
                    with factory() as db:
                        yield db
                app.dependency_overrides[get_db] = database
                app.dependency_overrides[current_user] = lambda: {"role": "STATE_OFFICER", "state": "Odisha", "district": None, "project_ids": []}
                with TestClient(app, headers={"X-LandGuard-Request": "1"}) as client:
                    assert client.get("/api/v1/health").status_code == 200
                    projects_response = client.get("/api/v1/projects")
                    assert projects_response.status_code == 200

                    payload = projects_response.json()

                    assert payload["total"] >= len(seed.SEEDS)
                    original = client.get("/api/v1/projects/P-RGD-001").json()
                    payload = {key: original[key] for key in seed.ProjectWrite.model_fields}
                    payload.update(project_id="PGVERIFY", project_name="Fictional PostgreSQL check")
                    assert client.post("/api/v1/projects", json=payload).status_code == 201
                    assert client.post("/api/v1/projects", json=payload).status_code == 409
                    payload.update(longitude=74.0, latitude=19.0)
                    assert client.put("/api/v1/projects/PGVERIFY", json=payload).status_code == 200
                    point = connection.execute(text(
                        "SELECT ST_X(location), ST_Y(location), ST_SRID(location) "
                        "FROM project_locations WHERE project_id = :pid"
                    ), {"pid": "PGVERIFY"}).one()
                    assert tuple(point) == (74.0, 19.0, 4326)
                    spatial_index = connection.scalar(text(
                        "SELECT count(*) FROM pg_indexes WHERE schemaname = :schema AND indexname = 'ix_projects_location_gist'"
                    ), {"schema": schema})
                    assert spatial_index == 1
                    bounded = client.get("/api/v1/map-data?min_lat=18&max_lat=20&min_lon=73&max_lon=75")
                    assert bounded.status_code == 200
                    assert any(row["project_id"] == "PGVERIFY" for row in bounded.json())
                    expected = len(seed.SEEDS) + 1
                    assert client.get("/api/v1/dashboard/summary").json()["total_projects"] == expected
                    for endpoint, count_key in (("district-summary", "project_count"), ("stage-distribution", "count")):
                        response = client.get(f"/api/v1/dashboard/{endpoint}")
                        assert response.status_code == 200
                        assert sum(row[count_key] for row in response.json()) == expected
                    assert client.get("/api/v1/dashboard/operational-risks").status_code == 200
                    assert client.delete("/api/v1/projects/PGVERIFY").status_code == 204
                    assert client.get("/api/v1/projects/PGVERIFY").status_code == 404
                return {"status": "passed", "postgis": version, "seed_records": len(seed.SEEDS)}
            finally:
                seed.SessionLocal = original_factory
                app.dependency_overrides.clear()
                app.dependency_overrides.update(original_overrides)
                connection.rollback()
                connection.execute(text("SET search_path TO public"))
                # This unique schema was created by this invocation, never supplied by a user.
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                connection.commit()
    finally:
        engine.dispose()


def main():
    url = os.environ.get("TEST_POSTGRES_URL", settings.database_url)
    if not url.startswith("postgresql"):
        print("PostgreSQL runtime verification could not be completed: no PostgreSQL DATABASE_URL or TEST_POSTGRES_URL is configured.")
        return 2
    try:
        print(verify_postgres(url))
    except OperationalError:
        print("PostgreSQL runtime verification could not be completed because the service was unavailable or rejected the connection.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
