from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import OPERATIONAL_ROLES, assert_project_access, scope_projects
from app.core.security import require_roles
from app.db.session import get_db
from app.models.project import Project
from app.services.intervention_automation_service import evaluate_all_projects, evaluate_project
from app.services.project_service import get_project

router = APIRouter(tags=["intervention automation"])
Database = Annotated[Session, Depends(get_db)]


class AutomationResult(BaseModel):
    projects_evaluated: int = Field(ge=0)
    created: int = Field(ge=0)
    condition_cleared: int = Field(ge=0)
    reminded: int = Field(ge=0)
    escalated: int = Field(ge=0)


@router.post("/projects/{project_id}/automation/evaluate")
def evaluate_project_automation(
    project_id: str,
    db: Database,
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    project = get_project(db, project_id)
    assert_project_access(project, user)
    return evaluate_project(db, project)


@router.post("/automation/run", response_model=AutomationResult)
def run_scoped_automation(
    db: Database,
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    projects = list(db.scalars(scope_projects(select(Project), user)).all())
    return evaluate_all_projects(db, projects)
