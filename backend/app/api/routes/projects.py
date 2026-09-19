from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, assert_project_access
from app.api.filters import Filters
from app.models.project import Project
from app.schemas.project import (
    AcquisitionStage, ProjectPage, ProjectRead, ProjectSortField, ProjectType, ProjectWrite, SortDirection,
)
from app.services.project_service import get_project, save_project

router = APIRouter(prefix="/projects", tags=["projects"])
Database = Annotated[Session, Depends(get_db)]

SORT_COLUMNS = {
    ProjectSortField.PROJECT_ID: Project.project_id,
    ProjectSortField.PROJECT_NAME: Project.project_name,
    ProjectSortField.STATE: Project.state,
    ProjectSortField.DISTRICT: Project.district,
    ProjectSortField.PROJECT_TYPE: Project.project_type,
    ProjectSortField.ACQUISITION_STAGE: Project.acquisition_stage,
    ProjectSortField.COMPENSATION_COMPLETION_PCT: Project.compensation_completion_pct,
    ProjectSortField.POSSESSION_PCT: Project.possession_pct,
    ProjectSortField.REHABILITATION_COMPLETION_PCT: Project.rehabilitation_completion_pct,
    ProjectSortField.PENDING_APPROVALS: Project.pending_approvals,
    ProjectSortField.LEGAL_DISPUTES: Project.legal_disputes,
    ProjectSortField.STAKEHOLDER_RESPONSE_DAYS: Project.stakeholder_response_days,
    ProjectSortField.ELAPSED_ACQUISITION_DAYS: Project.elapsed_acquisition_days,
}


@router.get("", response_model=ProjectPage)
def list_projects(db: Database, filters: Filters,
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  sort_by: ProjectSortField = ProjectSortField.PROJECT_ID,
                  sort_dir: SortDirection = SortDirection.ASC):
    query = filters.apply(select(Project))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    column = SORT_COLUMNS[sort_by]
    ordering = column.asc() if sort_dir is SortDirection.ASC else column.desc()
    items = db.scalars(
        query.order_by(ordering, Project.project_id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectWrite, db: Database, user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = Project(**payload.model_dump())
    assert_project_access(project, user)
    return save_project(db, project)


@router.get("/{project_id}", response_model=ProjectRead)
def read_project(project_id: str, db: Database, user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id)
    assert_project_access(project, user)
    return project


@router.put("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectWrite, db: Database, user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id)
    assert_project_access(project, user)
    assert_project_access(Project(**payload.model_dump()), user)
    for field, value in payload.model_dump().items():
        setattr(project, field, value)
    return save_project(db, project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Database, user=Depends(require_roles("STATE_OFFICER"))):
    project = get_project(db, project_id)
    assert_project_access(project, user)
    db.delete(project)
    db.commit()
    return Response(status_code=204)
