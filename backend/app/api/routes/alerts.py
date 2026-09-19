from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, scope_projects
from app.models.project import Project

router = APIRouter(tags=["alerts"])


class Alert(BaseModel):
    id: str
    project_id: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    title: str
    message: str
    created_at: datetime
    source: Literal["OPERATIONAL_RULE"] = "OPERATIONAL_RULE"


def project_alert(project: Project) -> Alert:
    severity = "CRITICAL" if project.legal_disputes >= 2 or project.pending_approvals >= 3 else "WARNING"
    factors = []
    if project.pending_approvals:
        factors.append(f"{project.pending_approvals} pending approval(s)")
    if project.legal_disputes:
        factors.append(f"{project.legal_disputes} legal dispute(s)")
    return Alert(
        id=f"operational-{project.project_id}", project_id=project.project_id, severity=severity,
        title="Administrative review recommended", message=" Â· ".join(factors),
        created_at=project.updated_at if project.updated_at else datetime.now(timezone.utc),
    )


@router.get("/alerts", response_model=list[Alert])
def alerts(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(*OPERATIONAL_ROLES))):
    projects = db.scalars(scope_projects(select(Project), user).where(or_(Project.pending_approvals > 0, Project.legal_disputes > 0)).order_by(Project.updated_at.desc())).all()
    return [project_alert(p) for p in projects]
