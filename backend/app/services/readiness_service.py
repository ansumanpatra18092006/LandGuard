from app.models.project import Project
from app.schemas.readiness import ReadinessComponent, ReadinessResult


def _pct(value) -> int:
    return max(0, min(100, round(float(value or 0))))


def _value(project: Project, field: str, overrides: dict | None):
    if overrides and field in overrides and overrides[field] is not None:
        return overrides[field]
    return getattr(project, field)


def readiness_for(project: Project, overrides: dict | None = None) -> ReadinessResult:
    compensation = _pct(_value(project, "compensation_completion_pct", overrides))
    possession = _pct(_value(project, "possession_pct", overrides))
    rehabilitation = _pct(_value(project, "rehabilitation_completion_pct", overrides))
    approvals = int(_value(project, "pending_approvals", overrides) or 0)
    disputes = int(_value(project, "legal_disputes", overrides) or 0)

    administrative = max(0, 100 - approvals * 15 - disputes * 30)
    components = [
        ReadinessComponent(key="compensation", label="Compensation", score=compensation, weight=.30,
                           note="Recorded compensation completion."),
        ReadinessComponent(key="possession", label="Possession", score=possession, weight=.35,
                           note="Recorded land-possession completion."),
        ReadinessComponent(key="rehabilitation", label="R&R", score=rehabilitation, weight=.15,
                           note="Recorded rehabilitation completion."),
        ReadinessComponent(key="administrative", label="Administrative clearance", score=administrative, weight=.20,
                           note=f"Prototype clearance score from {approvals} pending approvals and {disputes} legal disputes."),
    ]
    score = round(sum(c.score * c.weight for c in components))

    if disputes > 0:
        blocker = "Legal resolution"
    elif approvals > 0:
        blocker = "Approval clearance"
    elif compensation < 80:
        blocker = "Compensation"
    elif possession < 80:
        blocker = "Possession"
    elif rehabilitation < 80:
        blocker = "Rehabilitation / R&R"
    else:
        blocker = "No dominant recorded blocker"

    if compensation < 80:
        next_milestone = "Advance compensation processing"
    elif possession < 80:
        next_milestone = "Advance possession / handover readiness"
    elif rehabilitation < 80:
        next_milestone = "Complete rehabilitation obligations"
    elif approvals > 0 or disputes > 0:
        next_milestone = "Close administrative blockers"
    else:
        next_milestone = "Prepare handover / routine monitoring"

    if score >= 80 and approvals == 0 and disputes == 0 and possession >= 80:
        label = "READY"
    elif score < 50 or disputes > 0 or possession < 40:
        label = "BLOCKED"
    else:
        label = "CONSTRAINED"

    return ReadinessResult(
        project_id=project.project_id,
        readiness_score=score,
        readiness_label=label,
        primary_blocker=blocker,
        next_milestone=next_milestone,
        handover_readiness=label,
        components=components,
        methodology=("Transparent prototype readiness index: 30% compensation, 35% possession, 15% rehabilitation/R&R, "
                     "20% administrative clearance. It is deterministic decision-support logic, not an ML prediction or government standard."),
    )
