from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90"),
        CheckConstraint("longitude BETWEEN -180 AND 180"),
        *[CheckConstraint(f"{field} BETWEEN 0 AND 100") for field in (
            "compensation_completion_pct", "possession_pct", "rehabilitation_completion_pct")],
        *[CheckConstraint(f"{field} >= 0") for field in (
            "land_area", "affected_families", "pending_approvals", "legal_disputes",
            "stakeholder_response_days", "elapsed_acquisition_days")],
        CheckConstraint("original_cost_crore IS NULL OR original_cost_crore >= 0", name="ck_projects_original_cost_nonnegative"),
        CheckConstraint("expenditure_crore IS NULL OR expenditure_crore >= 0", name="ck_projects_expenditure_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    project_name: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[str] = mapped_column(String(40))
    state: Mapped[str] = mapped_column(String(100), index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    land_area: Mapped[float] = mapped_column(Float)
    affected_families: Mapped[int] = mapped_column(Integer)
    compensation_completion_pct: Mapped[float] = mapped_column(Float)
    pending_approvals: Mapped[int] = mapped_column(Integer)
    legal_disputes: Mapped[int] = mapped_column(Integer)
    possession_pct: Mapped[float] = mapped_column(Float)
    rehabilitation_completion_pct: Mapped[float] = mapped_column(Float)
    stakeholder_response_days: Mapped[int] = mapped_column(Integer)
    elapsed_acquisition_days: Mapped[int] = mapped_column(Integer)
    acquisition_stage: Mapped[str] = mapped_column(String(40))
    original_cost_crore: Mapped[float | None] = mapped_column(Float, nullable=True)
    expenditure_crore: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_source: Mapped[str] = mapped_column(String(40), default="USER_ENTERED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
