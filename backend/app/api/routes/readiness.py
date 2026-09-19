from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.access import OPERATIONAL_ROLES, assert_project_access
from app.core.security import require_roles
from app.db.session import get_db
from app.schemas.readiness import ReadinessResult
from app.services.project_service import get_project
from app.services.readiness_service import readiness_for

router = APIRouter(prefix="/projects", tags=["readiness"])


@router.get("/{project_id}/readiness", response_model=ReadinessResult)
def readiness(project_id: str, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, user)
    return readiness_for(project)
