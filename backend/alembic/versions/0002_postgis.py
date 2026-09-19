"""Prepare live PostGIS point locations without changing project CRUD."""
from alembic import op

revision = "0002_postgis"
down_revision = "0001_projects"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public")
        op.execute("""
            CREATE VIEW project_locations AS
            SELECT id, project_id, state, district,
                   ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geometry(Point,4326) AS location
            FROM projects
        """)


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP VIEW project_locations")
    # PostGIS can be shared with other applications; never drop the extension here.
