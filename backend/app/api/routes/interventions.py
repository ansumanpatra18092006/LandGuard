from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import OPERATIONAL_ROLES, assert_project_access
from app.core.security import require_roles
from app.db.session import get_db
from app.models.intervention import Intervention, InterventionEvent
from app.schemas.intervention import InterventionCreate, InterventionRead, InterventionUpdate
from app.services.project_service import get_project

router = APIRouter(prefix="/projects", tags=["interventions"])
Database = Annotated[Session, Depends(get_db)]


def _actor(user) -> str:
    return user.get("display_name") or user.get("email") or user.get("id") or "Authorized officer"


def _event(db: Session, intervention: Intervention, event_type: str, actor: str, detail: str):
    db.add(InterventionEvent(intervention_id=intervention.id, project_id=intervention.project_id,
                             event_type=event_type, actor=actor, detail=detail))


def _serialize(db: Session, intervention: Intervention) -> dict:
    events = db.scalars(select(InterventionEvent).where(InterventionEvent.intervention_id == intervention.id)
                        .order_by(InterventionEvent.created_at.desc(), InterventionEvent.id.desc())).all()
    return {
        **{c.name: getattr(intervention, c.name) for c in Intervention.__table__.columns},
        "overdue": intervention.status != "RESOLVED" and intervention.due_date < date.today(),
        "events": events,
    }


@router.get("/{project_id}/interventions", response_model=list[InterventionRead])
def list_interventions(project_id: str, db: Database, user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, user)
    rows = db.scalars(select(Intervention).where(Intervention.project_id == project_id)
                      .order_by(Intervention.status, Intervention.due_date, Intervention.id.desc())).all()
    return [_serialize(db, row) for row in rows]


@router.post("/{project_id}/interventions", response_model=InterventionRead, status_code=201)
def create_intervention(project_id: str, payload: InterventionCreate, db: Database,
                        user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, user)
    if payload.due_date < date.today():
        raise HTTPException(422, "Due date cannot be in the past")
    actor = _actor(user)
    row = Intervention(project_id=project_id, created_by=actor, **payload.model_dump())
    db.add(row); db.flush()
    _event(db, row, "CREATED", actor, f"Assigned to {row.assigned_to}; due {row.due_date.isoformat()}.")
    db.commit(); db.refresh(row)
    return _serialize(db, row)


@router.patch("/{project_id}/interventions/{intervention_id}", response_model=InterventionRead)
def update_intervention(project_id: str, intervention_id: int, payload: InterventionUpdate, db: Database,
                        user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, user)
    row = db.scalar(select(Intervention).where(Intervention.id == intervention_id, Intervention.project_id == project_id))
    if row is None:
        raise HTTPException(404, "Intervention not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("due_date") and changes["due_date"] < date.today() and row.status != "RESOLVED":
        raise HTTPException(422, "Due date cannot be in the past")
    old_status = row.status
    for key, value in changes.items():
        setattr(row, key, value)
    actor = _actor(user)
    if row.status == "RESOLVED" and old_status != "RESOLVED":
        row.resolved_at = datetime.now(timezone.utc)
        _event(db, row, "RESOLVED", actor, row.resolution_note or "Marked resolved.")
    elif row.status != old_status:
        _event(db, row, "STATUS_CHANGED", actor, f"Status changed from {old_status} to {row.status}.")
    else:
        _event(db, row, "UPDATED", actor, "Assignment, due date, priority or note updated.")
    db.commit(); db.refresh(row)
    return _serialize(db, row)


from app.core.access import scope_projects
from app.models.project import Project
from app.schemas.intervention import InterventionSummary

summary_router = APIRouter(prefix="/interventions", tags=["interventions"])


@summary_router.get("/summary", response_model=InterventionSummary)
def intervention_summary(db: Database, user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project_ids = list(db.scalars(scope_projects(select(Project.project_id), user)).all())
    if not project_ids:
        return InterventionSummary(open_count=0, overdue_count=0, in_progress_count=0, resolved_count=0)
    rows = db.scalars(select(Intervention).where(Intervention.project_id.in_(project_ids))).all()
    today = date.today()
    return InterventionSummary(
        open_count=sum(r.status == "OPEN" for r in rows),
        in_progress_count=sum(r.status == "IN_PROGRESS" for r in rows),
        resolved_count=sum(r.status == "RESOLVED" for r in rows),
        overdue_count=sum(r.status != "RESOLVED" and r.due_date < today for r in rows),
    )
