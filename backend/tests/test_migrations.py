from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text
from io import StringIO

from app.core.config import BACKEND_DIR
from app.core.config import settings
from app.db.base import Base
from app.db.init_db import migrate


def test_fresh_upgrade_and_downgrade(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migrate.db'}")
    with engine.begin() as connection:
        migrate(connection)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005_intervention_ledger"
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert not inspect(connection).has_table("projects")
        command.upgrade(config, "head")
        assert inspect(connection).has_table("projects")
    engine.dispose()


def test_legacy_adoption_preserves_records(database, client, payload):
    client.post("/api/v1/projects", json=payload)
    with database.kw["bind"].begin() as connection:
        with pytest.raises(RuntimeError, match="Unversioned"):
            migrate(connection)
        migrate(connection, adopt_legacy=True)
        assert connection.scalar(text("SELECT count(*) FROM projects")) == 1
        migrate(connection)
        assert connection.scalar(text("SELECT project_id FROM projects")) == "TEST01"


def test_legacy_schema_drift_is_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'drift.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="cannot be automatically verified"):
            migrate(connection, adopt_legacy=True)
        assert not inspect(connection).has_table("alembic_version")
    engine.dispose()


def test_postgresql_migration_sql(monkeypatch):
    # Compile the PostgreSQL branch without pretending this is a runtime connection.
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost/landguard")
    output = StringIO()
    config = Config(str(BACKEND_DIR / "alembic.ini"), output_buffer=output)
    config.attributes["version_table_schema"] = "integration_schema"
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE projects" in sql
    assert "CREATE TABLE integration_schema.alembic_version" in sql
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql
    assert "CREATE VIEW project_locations" in sql
    assert "ST_MakePoint(longitude, latitude)" in sql
    assert "geometry(Point,4326)" in sql
    assert "ix_projects_location_gist" in sql
    assert "USING GIST" in sql
