"""Persist intervention assignments and immutable intervention events."""
from alembic import op
import sqlalchemy as sa

revision = "0005_intervention_ledger"
down_revision = "0004_paimana_prediction_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=40), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=220), nullable=False),
        sa.Column("assigned_to", sa.String(length=160), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="OFFICER"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('OPEN','IN_PROGRESS','RESOLVED')", name="ck_interventions_status"),
        sa.CheckConstraint("priority IN ('LOW','MEDIUM','HIGH')", name="ck_interventions_priority"),
    )
    op.create_index("ix_interventions_project_id", "interventions", ["project_id"])
    op.create_index("ix_interventions_status", "interventions", ["status"])
    op.create_table(
        "intervention_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intervention_id", sa.Integer(), sa.ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_intervention_events_intervention_id", "intervention_events", ["intervention_id"])
    op.create_index("ix_intervention_events_project_id", "intervention_events", ["project_id"])


def downgrade():
    op.drop_index("ix_intervention_events_project_id", table_name="intervention_events")
    op.drop_index("ix_intervention_events_intervention_id", table_name="intervention_events")
    op.drop_table("intervention_events")
    op.drop_index("ix_interventions_status", table_name="interventions")
    op.drop_index("ix_interventions_project_id", table_name="interventions")
    op.drop_table("interventions")
