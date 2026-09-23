from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class LandParcel(Base):
    __tablename__ = "land_parcels"
    __table_args__ = (
        Index("ix_land_parcels_location", "state", "district"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(100), index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    tahasil: Mapped[str | None] = mapped_column(String(120), nullable=True)
    village: Mapped[str | None] = mapped_column(String(160), nullable=True)
    plot_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    khata_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unique_plot_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ownership_type: Mapped[str] = mapped_column(String(40), index=True)
    government_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tenant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kisam: Mapped[str | None] = mapped_column(String(120), nullable=True)
    area_acres: Mapped[float] = mapped_column(Float, default=0)
    ror_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source_name: Mapped[str] = mapped_column(String(120), default="CADASTRAL_IMPORT")
    source_record_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    geometry_geojson: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
