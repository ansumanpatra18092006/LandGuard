from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class ProjectSnapshot(Base):
    __tablename__ = "project_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(100), index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    acquisition_stage: Mapped[str] = mapped_column(String(40))
    land_area: Mapped[float] = mapped_column(Float)
    affected_families: Mapped[int] = mapped_column(Integer)
    compensation_completion_pct: Mapped[float] = mapped_column(Float)
    pending_approvals: Mapped[int] = mapped_column(Integer)
    legal_disputes: Mapped[int] = mapped_column(Integer)
    possession_pct: Mapped[float] = mapped_column(Float)
    rehabilitation_completion_pct: Mapped[float] = mapped_column(Float)
    stakeholder_response_days: Mapped[int] = mapped_column(Integer)
    elapsed_acquisition_days: Mapped[int] = mapped_column(Integer)
    acquisition_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delay_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ProjectAuditEvent(Base):
    __tablename__ = "project_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(240), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="LANDGUARD_UI")
    changed_fields: Mapped[str] = mapped_column(Text, default="[]")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
