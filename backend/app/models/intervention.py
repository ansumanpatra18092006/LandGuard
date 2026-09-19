from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Intervention(Base):
    __tablename__ = "interventions"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN','IN_PROGRESS','RESOLVED')", name="ck_interventions_status"),
        CheckConstraint("priority IN ('LOW','MEDIUM','HIGH')", name="ck_interventions_priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), ForeignKey("projects.project_id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(220))
    assigned_to: Mapped[str] = mapped_column(String(160))
    due_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    source: Mapped[str] = mapped_column(String(40), default="OFFICER")
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterventionEvent(Base):
    __tablename__ = "intervention_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intervention_id: Mapped[int] = mapped_column(Integer, ForeignKey("interventions.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
