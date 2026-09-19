from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, scope_projects
from app.models.project import Project
from app.schemas.project import ProjectPage

router = APIRouter(tags=["prototype notices"])


@router.get("/review-notices", response_model=ProjectPage)
def review_notices(db: Annotated[Session, Depends(get_db)], limit: int = Query(20, ge=1, le=100), user=Depends(require_roles(*OPERATIONAL_ROLES))):
    """Current review observations, not generated alerts or prediction events.

    Project updated_at is the record timestamp, not a notification timestamp.
    Read state belongs to the local browser in this prototype.
    """
    query = scope_projects(select(Project), user).where(or_(Project.pending_approvals > 0, Project.legal_disputes > 0))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Project.updated_at.desc(), Project.project_id).limit(limit)).all()
    return {"items": items, "total": total, "page": 1, "page_size": limit}
