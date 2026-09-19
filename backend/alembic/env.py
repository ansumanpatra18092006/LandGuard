from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base
from app.models.project import Project  # noqa: F401 - metadata registration
from app.models.intervention import Intervention, InterventionEvent  # noqa: F401 - metadata registration

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # PostGIS owns these objects; Alembic must not propose dropping them.
    return not (type_ == "table" and name in {"spatial_ref_sys", "geometry_columns", "geography_columns"})


def run(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      include_object=include_object, compare_type=True,
                      version_table_schema=context.config.attributes.get("version_table_schema"))
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      version_table_schema=context.config.attributes.get("version_table_schema"))
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    run(context.config.attributes["connection"])
else:
    engine = create_engine(settings.database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
