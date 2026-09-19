"""Add a GiST expression index for project point lookups."""
from alembic import op

revision = "0003_gis_spatial_index"
down_revision = "0002_postgis"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_projects_location_gist
            ON projects USING GIST (
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            )
        """)


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_projects_location_gist")
