from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, scope_projects
from app.models.project import Project
from app.schemas.gis import MapProject
from app.services.intelligence_service import risk_snapshot

router = APIRouter(tags=["GIS"])


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine fallback used for SQLite/tests and response display."""
    radius = 6371.0088
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return radius * 2 * asin(sqrt(a))


def _as_map_project(project: Project, distance_km: float | None = None) -> MapProject:
    risk = risk_snapshot(project)
    return MapProject(
        project_id=project.project_id,
        project_name=project.project_name,
        state=project.state,
        district=project.district,
        latitude=project.latitude,
        longitude=project.longitude,
        acquisition_stage=project.acquisition_stage,
        pending_approvals=project.pending_approvals,
        legal_disputes=project.legal_disputes,
        compensation_completion_pct=project.compensation_completion_pct,
        possession_pct=project.possession_pct,
        rehabilitation_completion_pct=project.rehabilitation_completion_pct,
        project_type=project.project_type,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
        delay_probability=risk["delay_probability"] if risk else None,
        risk_category=risk["risk_category"] if risk else None,
        slip_alert=risk["slip_alert"] if risk else None,
    )


@router.get("/map-data", response_model=list[MapProject])
def map_data(
    db: Annotated[Session, Depends(get_db)],
    state: str | None = Query(None, max_length=100),
    district: str | None = Query(None, max_length=100),
    stage: str | None = Query(None, max_length=40),
    min_lat: float | None = Query(None, ge=-90, le=90),
    max_lat: float | None = Query(None, ge=-90, le=90),
    min_lon: float | None = Query(None, ge=-180, le=180),
    max_lon: float | None = Query(None, ge=-180, le=180),
    near_lat: float | None = Query(None, ge=-90, le=90),
    near_lon: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, gt=0, le=1000),
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    bbox_values = (min_lat, max_lat, min_lon, max_lon)
    if any(value is not None for value in bbox_values) and not all(value is not None for value in bbox_values):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="All map bounds must be supplied together.")
    if min_lat is not None and (min_lat > max_lat or min_lon > max_lon):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Map bounds are invalid.")
    nearby_values = (near_lat, near_lon, radius_km)
    if any(value is not None for value in nearby_values) and not all(value is not None for value in nearby_values):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="near_lat, near_lon and radius_km must be supplied together.")

    query = scope_projects(select(Project), user)
    if state:
        query = query.where(Project.state == state)
    if district:
        query = query.where(Project.district == district)
    if stage:
        query = query.where(Project.acquisition_stage == stage)

    dialect = db.get_bind().dialect.name
    point = func.ST_SetSRID(func.ST_MakePoint(Project.longitude, Project.latitude), 4326)
    if min_lat is not None:
        if dialect == "postgresql":
            envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = query.where(func.ST_Intersects(point, envelope))
        else:
            query = query.where(
                Project.latitude.between(min_lat, max_lat),
                Project.longitude.between(min_lon, max_lon),
            )

    if near_lat is not None and dialect == "postgresql":
        origin = func.ST_SetSRID(func.ST_MakePoint(near_lon, near_lat), 4326)
        query = query.where(func.ST_DistanceSphere(point, origin) <= radius_km * 1000)

    projects = db.scalars(query.order_by(Project.state, Project.district, Project.project_id)).all()
    result = []
    for project in projects:
        distance = None
        if near_lat is not None:
            distance = _distance_km(near_lat, near_lon, project.latitude, project.longitude)
            if dialect != "postgresql" and distance > radius_km:
                continue
        result.append(_as_map_project(project, distance))
    return result
