"""Add cadastral/RoR ownership parcel storage."""
from alembic import op
import sqlalchemy as sa

revision = "0006_land_ownership_parcels"
down_revision = "0005_intervention_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "land_parcels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parcel_id", sa.String(80), nullable=False),
        sa.Column("project_id", sa.String(40), nullable=True),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("district", sa.String(100), nullable=False),
        sa.Column("tahasil", sa.String(120), nullable=True),
        sa.Column("village", sa.String(160), nullable=True),
        sa.Column("plot_no", sa.String(80), nullable=True),
        sa.Column("khata_no", sa.String(80), nullable=True),
        sa.Column("unique_plot_id", sa.String(120), nullable=True),
        sa.Column("ownership_type", sa.String(40), nullable=False),
        sa.Column("government_category", sa.String(120), nullable=True),
        sa.Column("tenant_name", sa.String(200), nullable=True),
        sa.Column("kisam", sa.String(120), nullable=True),
        sa.Column("area_acres", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ror_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_name", sa.String(120), nullable=False, server_default="CADASTRAL_IMPORT"),
        sa.Column("source_record_id", sa.String(160), nullable=True),
        sa.Column("geometry_geojson", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_land_parcels_parcel_id", "land_parcels", ["parcel_id"], unique=True)
    op.create_index("ix_land_parcels_project_id", "land_parcels", ["project_id"])
    op.create_index("ix_land_parcels_state", "land_parcels", ["state"])
    op.create_index("ix_land_parcels_district", "land_parcels", ["district"])
    op.create_index("ix_land_parcels_ownership_type", "land_parcels", ["ownership_type"])
    op.create_index("ix_land_parcels_location", "land_parcels", ["state", "district"])


def downgrade():
    op.drop_table("land_parcels")
