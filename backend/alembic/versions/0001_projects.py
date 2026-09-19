"""Freeze the original Project schema; independent of future model edits."""
from alembic import op
import sqlalchemy as sa

revision = "0001_projects"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(40), nullable=False),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("project_type", sa.String(40), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("district", sa.String(100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("land_area", sa.Float(), nullable=False),
        sa.Column("affected_families", sa.Integer(), nullable=False),
        sa.Column("compensation_completion_pct", sa.Float(), nullable=False),
        sa.Column("pending_approvals", sa.Integer(), nullable=False),
        sa.Column("legal_disputes", sa.Integer(), nullable=False),
        sa.Column("possession_pct", sa.Float(), nullable=False),
        sa.Column("rehabilitation_completion_pct", sa.Float(), nullable=False),
        sa.Column("stakeholder_response_days", sa.Integer(), nullable=False),
        sa.Column("elapsed_acquisition_days", sa.Integer(), nullable=False),
        sa.Column("acquisition_stage", sa.String(40), nullable=False),
        sa.Column("data_source", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180"),
        *[sa.CheckConstraint(f"{field} BETWEEN 0 AND 100") for field in (
            "compensation_completion_pct", "possession_pct", "rehabilitation_completion_pct")],
        *[sa.CheckConstraint(f"{field} >= 0") for field in (
            "land_area", "affected_families", "pending_approvals", "legal_disputes",
            "stakeholder_response_days", "elapsed_acquisition_days")],
    )
    op.create_index("ix_projects_project_id", "projects", ["project_id"], unique=True)
    op.create_index("ix_projects_state", "projects", ["state"])
    op.create_index("ix_projects_district", "projects", ["district"])


def downgrade():
    op.drop_table("projects")
