"""Add schedule-baseline inputs required by the real PAIMANA model."""
from alembic import op
import sqlalchemy as sa

revision = "0004_paimana_prediction_fields"
down_revision = "0003_gis_spatial_index"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("original_cost_crore", sa.Float(), nullable=True))
        batch.add_column(sa.Column("expenditure_crore", sa.Float(), nullable=True))
        batch.add_column(sa.Column("original_end_date", sa.Date(), nullable=True))
        batch.create_check_constraint("ck_projects_original_cost_nonnegative", "original_cost_crore IS NULL OR original_cost_crore >= 0")
        batch.create_check_constraint("ck_projects_expenditure_nonnegative", "expenditure_crore IS NULL OR expenditure_crore >= 0")


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("ck_projects_expenditure_nonnegative", type_="check")
        batch.drop_constraint("ck_projects_original_cost_nonnegative", type_="check")
        batch.drop_column("original_end_date")
        batch.drop_column("expenditure_crore")
        batch.drop_column("original_cost_crore")
