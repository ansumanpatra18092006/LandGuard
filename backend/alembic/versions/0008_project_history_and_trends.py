"""Add project snapshots and operational project audit history."""
from alembic import op
import sqlalchemy as sa

revision = "0008_project_history_and_trends"
down_revision = "0007_cadastral_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=40), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("acquisition_stage", sa.String(length=40), nullable=False),
        sa.Column("land_area", sa.Float(), nullable=False),
        sa.Column("affected_families", sa.Integer(), nullable=False),
        sa.Column("compensation_completion_pct", sa.Float(), nullable=False),
        sa.Column("pending_approvals", sa.Integer(), nullable=False),
        sa.Column("legal_disputes", sa.Integer(), nullable=False),
        sa.Column("possession_pct", sa.Float(), nullable=False),
        sa.Column("rehabilitation_completion_pct", sa.Float(), nullable=False),
        sa.Column("stakeholder_response_days", sa.Integer(), nullable=False),
        sa.Column("elapsed_acquisition_days", sa.Integer(), nullable=False),
        sa.Column("acquisition_risk_score", sa.Integer(), nullable=True),
        sa.Column("delay_probability", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_snapshots_project_id", "project_snapshots", ["project_id"])
    op.create_index("ix_project_snapshots_state", "project_snapshots", ["state"])
    op.create_index("ix_project_snapshots_district", "project_snapshots", ["district"])
    op.create_index("ix_project_snapshots_captured_at", "project_snapshots", ["captured_at"])

    op.create_table(
        "project_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=True),
        sa.Column("actor_email", sa.String(length=240), nullable=True),
        sa.Column("actor_role", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="LANDGUARD_UI"),
        sa.Column("changed_fields", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_audit_events_project_id", "project_audit_events", ["project_id"])
    op.create_index("ix_project_audit_events_event_type", "project_audit_events", ["event_type"])
    op.create_index("ix_project_audit_events_created_at", "project_audit_events", ["created_at"])

    # Existing installations immediately get a baseline history point. Risk
    # values are populated on subsequent LandGuard updates, when the services
    # can calculate them with the currently loaded models.
    op.execute("""
        INSERT INTO project_snapshots (
            project_id, state, district, acquisition_stage, land_area, affected_families,
            compensation_completion_pct, pending_approvals, legal_disputes, possession_pct,
            rehabilitation_completion_pct, stakeholder_response_days, elapsed_acquisition_days,
            acquisition_risk_score, delay_probability, captured_at
        )
        SELECT project_id, state, district, acquisition_stage, land_area, affected_families,
               compensation_completion_pct, pending_approvals, legal_disputes, possession_pct,
               rehabilitation_completion_pct, stakeholder_response_days, elapsed_acquisition_days,
               NULL, NULL, COALESCE(updated_at, created_at)
        FROM projects
    """)


def downgrade():
    op.drop_index("ix_project_audit_events_created_at", table_name="project_audit_events")
    op.drop_index("ix_project_audit_events_event_type", table_name="project_audit_events")
    op.drop_index("ix_project_audit_events_project_id", table_name="project_audit_events")
    op.drop_table("project_audit_events")
    op.drop_index("ix_project_snapshots_captured_at", table_name="project_snapshots")
    op.drop_index("ix_project_snapshots_district", table_name="project_snapshots")
    op.drop_index("ix_project_snapshots_state", table_name="project_snapshots")
    op.drop_index("ix_project_snapshots_project_id", table_name="project_snapshots")
    op.drop_table("project_snapshots")
