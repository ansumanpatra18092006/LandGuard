import argparse

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.core.config import BACKEND_DIR
from app.db.base import Base
from app.db.session import engine
from app.models.project import Project  # noqa: F401


def migrate(connection, adopt_legacy: bool = False):
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    inspector = inspect(connection)
    if inspector.has_table("projects") and not inspector.has_table("alembic_version"):
        if not adopt_legacy:
            raise RuntimeError("Unversioned projects table found. Back up the database, then use --adopt-legacy.")
        def include(obj, name, kind, reflected, compare_to):
            return kind != "table" or name == "projects"
        differences = compare_metadata(MigrationContext.configure(connection, opts={"include_object": include}), Base.metadata)
        expected = {str(c.sqltext) for c in Project.__table__.constraints if hasattr(c, "sqltext")}
        actual = {c["sqltext"] for c in inspector.get_check_constraints("projects")}
        # SQLite preserves the original SQL. If an unversioned SQLite database
        # already matches the current model exactly, adopt it at head instead of
        # replaying column-add migrations and duplicating columns.
        if connection.dialect.name != "sqlite" or differences or actual != expected:
            raise RuntimeError("Legacy schema cannot be automatically verified. Review schema before stamping the current migration head.")
        command.stamp(config, "head")
    command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description="Run Alembic migrations; preserve existing records.")
    parser.add_argument("--adopt-legacy", action="store_true", help="Verify and version the original SQLite schema")
    args = parser.parse_args()
    with engine.begin() as connection:
        migrate(connection, args.adopt_legacy)
    print("Database migrated to head. Existing data preserved.")


if __name__ == "__main__":
    main()
