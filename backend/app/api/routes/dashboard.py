from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.filters import Filters
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary, DistrictSummary, OperationalIndicators, StageCount
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
