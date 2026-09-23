"""Remove synthetic cadastral ownership rows from earlier SIH demo builds.

Real parcel geometry must come from an imported/authorised cadastral source.
"""
from alembic import op

revision = "0007_cadastral_cleanup"
down_revision = "0007_project_ownership_type"
branch_labels = None
depends_on = None


def upgrade():
    # Existing installations may already contain the rectangular DEMO-* parcel
    # grid seeded by 0006-era builds. Remove only those explicitly synthetic rows.
    op.execute("DELETE FROM land_parcels WHERE source_name = 'ILLUSTRATIVE_SIH_DEMO' OR parcel_id LIKE 'DEMO-%'")


def downgrade():
    # Synthetic ownership must never be re-created during downgrade.
    pass
