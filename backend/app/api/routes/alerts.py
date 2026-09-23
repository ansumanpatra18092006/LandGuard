from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, scope_projects
from app.models.intervention import Intervention
from app.models.project import Project
from app.services.intervention_automation_service import apply_intervention_lifecycle
from app.services.intelligence_service import portfolio_risk_pulse

router = APIRouter(tags=["alerts"])


class Alert(BaseModel):
    id: str
    project_id: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    title: str
    message: str
    created_at: datetime
    source: Literal["OPERATIONAL_RULE", "AUTOMATION", "PREDICTIVE_MODEL"]


def project_alert(project: Project) -> Alert:
    severity = "CRITICAL" if project.legal_disputes >= 2 or project.pending_approvals >= 3 else "WARNING"
    factors = []
    if project.pending_approvals:
        factors.append(f"{project.pending_approvals} pending approval(s)")
    if project.legal_disputes:
        factors.append(f"{project.legal_disputes} legal dispute(s)")
    return Alert(
        id=f"operational-{project.project_id}", project_id=project.project_id, severity=severity,
        title="Administrative review recommended", message=" · ".join(factors),
        created_at=project.updated_at if project.updated_at else datetime.now(timezone.utc),
        source="OPERATIONAL_RULE",
    )


def intervention_alert(row: Intervention) -> Alert | None:
    if row.status == "RESOLVED":
        return None
    days_left = (row.due_date - date.today()).days
    if days_left < 0:
        return Alert(
            id=f"automation-overdue-{row.id}", project_id=row.project_id, severity="CRITICAL",
            title="Automated intervention overdue",
            message=f"{row.action} · owner: {row.assigned_to} · overdue by {abs(days_left)} day(s).",
            created_at=row.updated_at or row.created_at, source="AUTOMATION",
        )
    if days_left <= 2:
        return Alert(
            id=f"automation-due-{row.id}", project_id=row.project_id, severity="WARNING",
            title="Automated intervention due soon",
            message=f"{row.action} · owner: {row.assigned_to} · due in {days_left} day(s).",
            created_at=row.updated_at or row.created_at, source="AUTOMATION",
        )
    return None


@router.get("/alerts", response_model=list[Alert])
def alerts(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(*OPERATIONAL_ROLES))):
    apply_intervention_lifecycle(db)
    projects = list(db.scalars(
        scope_projects(select(Project), user)
        .where(or_(Project.pending_approvals > 0, Project.legal_disputes > 0))
        .order_by(Project.updated_at.desc())
    ).all())
    project_ids = list(db.scalars(scope_projects(select(Project.project_id), user)).all())
    rows = [] if not project_ids else list(db.scalars(
        select(Intervention).where(Intervention.project_id.in_(project_ids), Intervention.status != "RESOLVED")
    ).all())
    automation_alerts = [a for row in rows if (a := intervention_alert(row)) is not None]
    predictive_alerts = []
    try:
        pulse = portfolio_risk_pulse(projects)
        by_id = {project.project_id: project for project in projects}
        for item in pulse.projects:
            if item.risk_category != "HIGH" and not item.slip_alert:
                continue
            project = by_id.get(item.project_id)
            if project is None:
                continue
            predictive_alerts.append(Alert(
                id=f"predictive-{item.project_id}",
                project_id=item.project_id,
                severity="CRITICAL" if (item.delay_probability or 0) >= 0.75 else "WARNING",
                title="Predictive delay alert",
                message=(
                    f"PAIMANA schedule-slip signal {round((item.delay_probability or 0) * 100)}% · "
                    f"{item.risk_category} risk · next attention: {item.suggested_action or item.primary_bottleneck or 'review project intelligence'}."
                ),
                created_at=project.updated_at if project.updated_at else datetime.now(timezone.utc),
                source="PREDICTIVE_MODEL",
            ))
    except Exception:
        # Operational alerts must remain available even if the ML artifact is unavailable.
        predictive_alerts = []
    return [*automation_alerts, *[project_alert(p) for p in projects], *predictive_alerts]
