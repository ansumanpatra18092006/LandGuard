from __future__ import annotations

from dataclasses import dataclass

from app.models.project import Project


@dataclass(frozen=True)
class FrictionSnapshot:
    score: int
    label: str
    components: list[dict]
    dominant_blocker: str
    methodology: str


def _pct(value) -> float:
    return max(0.0, min(100.0, float(value or 0)))


def _value(project: Project, field: str, overrides: dict | None):
    if overrides and field in overrides and overrides[field] is not None:
        return overrides[field]
    return getattr(project, field)


def friction_for(project: Project, overrides: dict | None = None) -> FrictionSnapshot:
    approvals = max(0, int(_value(project, "pending_approvals", overrides) or 0))
    disputes = max(0, int(_value(project, "legal_disputes", overrides) or 0))
    compensation = _pct(_value(project, "compensation_completion_pct", overrides))
    possession = _pct(_value(project, "possession_pct", overrides))
    rehabilitation = _pct(_value(project, "rehabilitation_completion_pct", overrides))
    response_days = max(0, int(_value(project, "stakeholder_response_days", overrides) or 0))

    # Transparent expert-prior prototype weights. This is intentionally not ML.
    components = [
        {
            "key": "legal_disputes",
            "label": "Legal disputes",
            "score": min(100, disputes * 40),
            "weight": 0.20,
            "note": f"{disputes} recorded dispute(s); capped at 100 friction points.",
        },
        {
            "key": "pending_approvals",
            "label": "Pending approvals",
            "score": min(100, approvals * 20),
            "weight": 0.15,
            "note": f"{approvals} recorded approval(s) pending; capped at 100 friction points.",
        },
        {
            "key": "compensation_gap",
            "label": "Compensation gap",
            "score": round(100 - compensation),
            "weight": 0.20,
            "note": f"Compensation is {round(compensation)}% complete.",
        },
        {
            "key": "possession_gap",
            "label": "Possession gap",
            "score": round(100 - possession),
            "weight": 0.20,
            "note": f"Possession is {round(possession)}% complete.",
        },
        {
            "key": "rehabilitation_gap",
            "label": "R&R gap",
            "score": round(100 - rehabilitation),
            "weight": 0.10,
            "note": f"Rehabilitation/R&R is {round(rehabilitation)}% complete.",
        },
        {
            "key": "stakeholder_response",
            "label": "Stakeholder response delay",
            "score": min(100, round(response_days / 45 * 100)),
            "weight": 0.15,
            "note": f"Recorded stakeholder response time is {response_days} day(s); 45+ days maps to maximum friction in this prototype.",
        },
    ]
    score = round(sum(float(c["score"]) * float(c["weight"]) for c in components))

    if score < 30:
        label = "LOW"
    elif score < 55:
        label = "MODERATE"
    elif score < 75:
        label = "HIGH"
    else:
        label = "CRITICAL"

    dominant = max(components, key=lambda c: float(c["score"]) * float(c["weight"]))
    return FrictionSnapshot(
        score=score,
        label=label,
        components=components,
        dominant_blocker=str(dominant["label"]),
        methodology=(
            "Transparent Land-Acquisition Friction Index using recorded operational indicators: "
            "20% legal disputes, 15% pending approvals, 20% compensation gap, 20% possession gap, "
            "10% rehabilitation/R&R gap, and 15% stakeholder-response delay. It is an expert-prior "
            "decision-support index, not a learned ML probability or government standard."
        ),
    )


def intervention_priority(schedule_probability: float, friction_score: int, readiness_score: int, acquisition_risk_score: int | None = None) -> tuple[int, str]:
    """Rank officer attention without allowing generic schedule evidence to hide LA risk.

    When the acquisition-specific index is available, it establishes the base priority.
    The independent PAIMANA schedule signal can *escalate* that priority by adding up to
    30% of the remaining headroom to 100. A low schedule signal therefore cannot pull a
    HIGH acquisition-risk case down to WATCH. The result is a transparent heuristic
    ranking score, not a probability.
    """
    schedule = max(0.0, min(100.0, float(schedule_probability) * 100.0))
    if acquisition_risk_score is not None:
        acquisition = max(0.0, min(100.0, float(acquisition_risk_score)))
        schedule_escalation = (100.0 - acquisition) * (schedule / 100.0) * 0.30
        score = round(min(100.0, acquisition + schedule_escalation))
    else:
        friction = max(0.0, min(100.0, float(friction_score)))
        readiness_gap = max(0.0, min(100.0, 100.0 - float(readiness_score)))
        operational_base = round(friction * 0.65 + readiness_gap * 0.35)
        schedule_escalation = (100.0 - operational_base) * (schedule / 100.0) * 0.30
        score = round(min(100.0, operational_base + schedule_escalation))
    if score < 30:
        label = "ROUTINE"
    elif score < 50:
        label = "WATCH"
    elif score < 70:
        label = "HIGH"
    else:
        label = "CRITICAL"
    return score, label
