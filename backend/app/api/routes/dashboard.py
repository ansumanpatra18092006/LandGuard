from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.filters import Filters
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary, DistrictSummary, OperationalIndicators, StageCount, DelayTrendPoint
from app.services import dashboard_service as service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Database, filters: Filters):
    return service.summary(db, filters)


@router.get("/district-summary", response_model=list[DistrictSummary])
def district_summary(db: Database, filters: Filters):
    return service.districts(db, filters)


@router.get("/stage-distribution", response_model=list[StageCount])
def stage_distribution(db: Database, filters: Filters):
    return service.stages(db, filters)


@router.get("/operational-risks", response_model=OperationalIndicators)
def operational_risks(db: Database, filters: Filters):
    return service.operational_indicators(db, filters)


@router.get("/delay-trends", response_model=list[DelayTrendPoint])
def delay_trends(
    db: Database,
    filters: Filters,
    group_by: str = Query("district", pattern="^(district|state)$"),
    days: int = Query(365, ge=7, le=1825),
):
    return service.delay_trends(db, filters, group_by=group_by, days=days)
