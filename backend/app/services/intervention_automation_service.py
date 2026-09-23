from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intervention import Intervention, InterventionEvent
from app.models.project import Project
from app.services.acquisition_risk_service import acquisition_delay_risk_for

AUTOMATION_ACTOR = "LandGuard Automation Engine"
AUTOMATION_SOURCE = "AUTOMATION"


@dataclass(frozen=True)
class AutomationRule:
    key: str
    action: str
    owner: str
    due_days: int
    priority: str
    active: bool
    reason: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _event_exists(db: Session, intervention_id: int, event_type: str) -> bool:
    return db.scalar(
        select(InterventionEvent.id)
        .where(
            InterventionEvent.intervention_id == intervention_id,
            InterventionEvent.event_type == event_type,
        )
        .limit(1)
    ) is not None


def _add_event(db: Session, row: Intervention, event_type: str, detail: str) -> None:
    db.add(
        InterventionEvent(
            intervention_id=row.id,
            project_id=row.project_id,
            event_type=event_type,
            actor=AUTOMATION_ACTOR,
            detail=detail,
        )
    )


def rules_for(project: Project) -> list[AutomationRule]:
    approvals = max(0, int(project.pending_approvals or 0))
    disputes = max(0, int(project.legal_disputes or 0))
    compensation = max(0.0, min(100.0, float(project.compensation_completion_pct or 0)))
    possession = max(0.0, min(100.0, float(project.possession_pct or 0)))
    rehabilitation = max(0.0, min(100.0, float(project.rehabilitation_completion_pct or 0)))
    response_days = max(0, int(project.stakeholder_response_days or 0))
    acquisition_risk = acquisition_delay_risk_for(project)

    return [
        AutomationRule(
            key="LEGAL_REVIEW",
            action="Legal review required",
            owner="District Legal Cell",
            due_days=3,
            priority="HIGH",
            active=disputes > 0,
            reason=f"{disputes} recorded legal dispute(s) require authorized review.",
        ),
        AutomationRule(
            key="APPROVAL_CLEARANCE",
            action="Approval clearance required",
            owner="District Acquisition Cell",
            due_days=5,
            priority="HIGH" if approvals >= 3 else "MEDIUM",
            active=approvals > 0,
            reason=f"{approvals} approval(s) remain pending.",
        ),
        AutomationRule(
            key="POSSESSION_REVIEW",
            action="Possession and handover review",
            owner="Revenue / Possession Cell",
            due_days=7,
            priority="HIGH" if possession < 30 else "MEDIUM",
            active=possession < 50,
            reason=f"Possession is {round(possession)}% complete, below the 50% automation trigger.",
        ),
        AutomationRule(
            key="COMPENSATION_FOLLOWUP",
            action="Compensation processing follow-up",
            owner="Compensation Cell",
            due_days=7,
            priority="HIGH" if compensation < 30 else "MEDIUM",
            active=compensation < 50,
            reason=f"Compensation is {round(compensation)}% complete, below the 50% automation trigger.",
        ),
        AutomationRule(
            key="RR_FOLLOWUP",
            action="R&R obligation follow-up",
            owner="R&R Cell",
            due_days=10,
            priority="MEDIUM",
            active=rehabilitation < 50,
            reason=f"R&R is {round(rehabilitation)}% complete, below the 50% automation trigger.",
        ),
        AutomationRule(
            key="STAKEHOLDER_RESPONSE",
            action="Stakeholder response escalation",
            owner="District Coordination Cell",
            due_days=5,
            priority="HIGH" if response_days >= 45 else "MEDIUM",
            active=response_days > 30,
            reason=f"Recorded stakeholder response time is {response_days} day(s), above the 30-day automation trigger.",
        ),
        AutomationRule(
            key="HIGH_ACQUISITION_RISK",
            action="High acquisition-risk review",
            owner="District Acquisition Officer",
            due_days=3,
            priority="HIGH",
            active=acquisition_risk.score >= 70,
            reason=f"Acquisition Delay Risk Index is {acquisition_risk.score}/100 ({acquisition_risk.label}).",
        ),
    ]


def _existing_for_rule(db: Session, project_id: str, action: str) -> list[Intervention]:
    return list(
        db.scalars(
            select(Intervention)
            .where(
                Intervention.project_id == project_id,
                Intervention.source == AUTOMATION_SOURCE,
                Intervention.action == action,
            )
            .order_by(Intervention.id.desc())
        ).all()
    )


def _resolved_after_last_project_update(row: Intervention, project: Project) -> bool:
    resolved_at = _aware(row.resolved_at)
    updated_at = _aware(project.updated_at)
    return bool(resolved_at and updated_at and resolved_at >= updated_at)


def evaluate_project(db: Session, project: Project, *, commit: bool = True) -> dict:
    """Evaluate deterministic operational automation rules for one project.

    The engine creates trackable actions but never auto-resolves them. If a trigger
    clears, it records that the condition appears cleared and leaves verification to
    an authorized officer.
    """
    created = 0
    condition_cleared = 0
    today = date.today()

    for rule in rules_for(project):
        existing = _existing_for_rule(db, project.project_id, rule.action)
        open_rows = [r for r in existing if r.status != "RESOLVED"]

        if rule.active:
            if open_rows:
                row = open_rows[0]
                # Automation may increase urgency but does not silently downgrade it.
                if rule.priority == "HIGH" and row.priority != "HIGH":
                    row.priority = "HIGH"
                    _add_event(db, row, "AUTOMATION_REPRIORITIZED", rule.reason)
                continue

            latest = existing[0] if existing else None
            # Do not immediately recreate an action that an officer resolved after
            # the most recent project record update. A later project update can
            # legitimately trigger the rule again if the condition remains.
            if latest and latest.status == "RESOLVED" and _resolved_after_last_project_update(latest, project):
                continue

            row = Intervention(
                project_id=project.project_id,
                action=rule.action,
                assigned_to=rule.owner,
                due_date=today + timedelta(days=rule.due_days),
                priority=rule.priority,
                status="OPEN",
                source=AUTOMATION_SOURCE,
                created_by=AUTOMATION_ACTOR,
            )
            db.add(row)
            db.flush()
            _add_event(
                db,
                row,
                "AUTO_CREATED",
                f"Rule {rule.key} triggered. {rule.reason} Assigned to {rule.owner}; due {row.due_date.isoformat()}.",
            )
            created += 1
        else:
            for row in open_rows:
                if not _event_exists(db, row.id, "CONDITION_CLEARED"):
                    _add_event(
                        db,
                        row,
                        "CONDITION_CLEARED",
                        "The recorded trigger condition is no longer active. Officer verification is required before closure.",
                    )
                    condition_cleared += 1

    lifecycle = apply_intervention_lifecycle(db, project_id=project.project_id, commit=False)
    if commit:
        db.commit()

    return {
        "project_id": project.project_id,
        "created": created,
        "condition_cleared": condition_cleared,
        **lifecycle,
    }


def apply_intervention_lifecycle(db: Session, *, project_id: str | None = None, commit: bool = True) -> dict:
    """Create one-time reminders and overdue escalations for unresolved actions."""
    query = select(Intervention).where(Intervention.status != "RESOLVED")
    if project_id:
        query = query.where(Intervention.project_id == project_id)
    rows = list(db.scalars(query).all())
    today = date.today()
    reminded = 0
    escalated = 0

    for row in rows:
        days_left = (row.due_date - today).days
        if days_left < 0:
            if not _event_exists(db, row.id, "OVERDUE_ESCALATED"):
                row.priority = "HIGH"
                _add_event(
                    db,
                    row,
                    "OVERDUE_ESCALATED",
                    f"Action is overdue by {abs(days_left)} day(s). Priority escalated to HIGH for officer attention.",
                )
                escalated += 1
        elif days_left <= 2 and not _event_exists(db, row.id, "DUE_REMINDER"):
            _add_event(
                db,
                row,
                "DUE_REMINDER",
                f"Action is due in {days_left} day(s). Reminder generated for {row.assigned_to}.",
            )
            reminded += 1

    if commit and (reminded or escalated):
        db.commit()
    return {"reminded": reminded, "escalated": escalated}


def evaluate_all_projects(db: Session, projects: list[Project] | None = None, *, commit: bool = True) -> dict:
    targets = projects if projects is not None else list(db.scalars(select(Project)).all())
    totals = {"projects_evaluated": 0, "created": 0, "condition_cleared": 0, "reminded": 0, "escalated": 0}
    for project in targets:
        result = evaluate_project(db, project, commit=False)
        totals["projects_evaluated"] += 1
        for key in ("created", "condition_cleared", "reminded", "escalated"):
            totals[key] += int(result.get(key, 0))
    if commit:
        db.commit()
    return totals
