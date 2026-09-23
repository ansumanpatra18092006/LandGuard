"""Compatibility bridge for installations stamped by the earlier ownership branch.

Some LandGuard builds created/stamped revision ``0007_project_ownership_type``.
The merged codebase stores parcel ownership in ``land_parcels`` (created by
0006), so this revision intentionally performs no schema operation.  It exists
only to preserve the historical Alembic revision chain for existing databases.
"""

revision = "0007_project_ownership_type"
down_revision = "0006_land_ownership_parcels"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
