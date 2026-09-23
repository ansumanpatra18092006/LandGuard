from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_audit import ProjectAuditEvent, ProjectSnapshot
from app.services.acquisition_risk_service import acquisition_delay_risk_for

TRACKED_FIELDS = (
    "project_name", "project_type", "state", "district", "latitude", "longitude",
    "land_area", "affected_families", "compensation_completion_pct", "pending_approvals",
    "legal_disputes", "possession_pct", "rehabilitation_completion_pct",
    "stakeholder_response_days", "elapsed_acquisition_days", "acquisition_stage",
    "original_cost_crore", "expenditure_crore", "original_end_date",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def project_state(project: Project) -> dict:
    return {field: getattr(project, field, None) for field in TRACKED_FIELDS}


def changed_fields(before: dict | None, after: dict | None) -> list[str]:
    before = before or {}
    after = after or {}
    return [field for field in TRACKED_FIELDS if before.get(field) != after.get(field)]


def _delay_probability(project: Project) -> float | None:
    try:
        from app.services.intelligence_service import predict
        return float(predict(project).delay_probability)
    except Exception:
        return None


def record_snapshot(db: Session, project: Project, *, captured_at: datetime | None = None) -> ProjectSnapshot:
    risk = acquisition_delay_risk_for(project)
    row = ProjectSnapshot(
        project_id=project.project_id,
        state=project.state,
        district=project.district,
        acquisition_stage=project.acquisition_stage,
        land_area=project.land_area,
        affected_families=project.affected_families,
        compensation_completion_pct=project.compensation_completion_pct,
        pending_approvals=project.pending_approvals,
        legal_disputes=project.legal_disputes,
        possession_pct=project.possession_pct,
        rehabilitation_completion_pct=project.rehabilitation_completion_pct,
        stakeholder_response_days=project.stakeholder_response_days,
        elapsed_acquisition_days=project.elapsed_acquisition_days,
        acquisition_risk_score=risk.score,
        delay_probability=_delay_probability(project),
        captured_at=captured_at or _now(),
    )
    db.add(row)
    return row


def record_audit(
    db: Session,
    *,
    project_id: str,
    event_type: str,
    user: dict | None,
    before: dict | None = None,
    after: dict | None = None,
    source: str = "LANDGUARD_UI",
    detail: str = "",
) -> ProjectAuditEvent:
    fields = changed_fields(before, after)
    row = ProjectAuditEvent(
        project_id=project_id,
        event_type=event_type,
        actor_id=str(user.get("id")) if user and user.get("id") else None,
        actor_email=str(user.get("email")) if user and user.get("email") else None,
        actor_role=str(user.get("role")) if user and user.get("role") else None,
        source=source[:80],
        changed_fields=json.dumps(fields),
        detail=detail[:2000],
        created_at=_now(),
    )
    db.add(row)
    return row


def history_for(db: Session, project_id: str) -> tuple[list[ProjectAuditEvent], list[ProjectSnapshot]]:
    events = list(db.scalars(
        select(ProjectAuditEvent)
        .where(ProjectAuditEvent.project_id == project_id)
        .order_by(ProjectAuditEvent.created_at.desc(), ProjectAuditEvent.id.desc())
        .limit(200)
    ).all())
    snapshots = list(db.scalars(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.captured_at.desc(), ProjectSnapshot.id.desc())
        .limit(200)
    ).all())
    return events, snapshots
