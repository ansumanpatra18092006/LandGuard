from __future__ import annotations

from dataclasses import dataclass

from app.models.project import Project
from app.services.friction_service import friction_for
from app.services.readiness_service import readiness_for


@dataclass(frozen=True)
class AcquisitionRiskSnapshot:
    score: int
    label: str
    current_stage: str
    stage_attention: str
    drivers: list[dict]
    methodology: str


def _value(project: Project, field: str, overrides: dict | None):
    if overrides and field in overrides and overrides[field] is not None:
        return overrides[field]
    return getattr(project, field)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _stage_attention(project: Project, dominant_blocker: str, overrides: dict | None = None) -> str:
    """Keep the attention message aligned with the blocker shown to the officer."""
    stage = str(_value(project, "acquisition_stage", overrides) or "UNKNOWN").upper()
    compensation = float(_value(project, "compensation_completion_pct", overrides) or 0)
    possession = float(_value(project, "possession_pct", overrides) or 0)
    rehabilitation = float(_value(project, "rehabilitation_completion_pct", overrides) or 0)

    actions = {
        "Legal disputes": "Resolve the recorded legal dispute and document the authorized legal follow-up before stage progression.",
        "Pending approvals": "Clear the pending administrative approvals that are constraining the acquisition workflow.",
        "Compensation gap": f"Compensation is {round(compensation)}% complete. Review unpaid or unresolved compensation cases before the next milestone.",
        "Possession gap": f"Possession is {round(possession)}% complete. Review remaining possession and lawful handover blockers.",
        "R&R gap": f"Rehabilitation/R&R is {round(rehabilitation)}% complete. Close pending R&R obligations before handover readiness.",
        "Stakeholder response delay": "Reduce stakeholder-response delay by assigning the pending follow-up to a responsible officer and due date.",
    }
    if dominant_blocker in actions:
        return actions[dominant_blocker]
    if stage == "COMPLETED":
        return "No current acquisition blocker is indicated by the recorded prototype fields."
    return "Review the current acquisition-stage evidence and unresolved operational conditions before progression."


def acquisition_delay_risk_for(project: Project, overrides: dict | None = None) -> AcquisitionRiskSnapshot:
    """Transparent land-acquisition-specific risk index.

    This deliberately is NOT presented as a learned probability. It exists because the
    PAIMANA model learns schedule behaviour, while the SIH problem requires acquisition-
    specific risk reasoning from compensation, possession, disputes, approvals, R&R and
    current acquisition context.
    """
    friction = friction_for(project, overrides)
    readiness = readiness_for(project, overrides=overrides)
    elapsed_days = max(0, int(_value(project, "elapsed_acquisition_days", overrides) or 0))
    land_area = max(0.0, float(_value(project, "land_area", overrides) or 0))
    affected_families = max(0, int(_value(project, "affected_families", overrides) or 0))

    # Prototype expert-prior pressure components. Thresholds are transparent UI heuristics,
    # not statutory deadlines or government-standard weights.
    elapsed_pressure = round(_clamp(elapsed_days / 540.0 * 100.0))
    land_scale = _clamp(land_area / 250.0 * 100.0)
    family_scale = _clamp(affected_families / 500.0 * 100.0)
    scale_complexity = round((land_scale + family_scale) / 2.0)
    readiness_gap = 100 - readiness.readiness_score

    drivers = [
        {
            "key": "acquisition_friction",
            "label": "Recorded acquisition friction",
            "score": friction.score,
            "weight": 0.50,
            "note": f"Operational friction is {friction.score}/100; dominant blocker: {friction.dominant_blocker}.",
        },
        {
            "key": "readiness_gap",
            "label": "Readiness gap",
            "score": readiness_gap,
            "weight": 0.25,
            "note": f"Acquisition readiness is {readiness.readiness_score}/100, leaving a {readiness_gap}-point gap.",
        },
        {
            "key": "elapsed_acquisition_pressure",
            "label": "Elapsed acquisition pressure",
            "score": elapsed_pressure,
            "weight": 0.15,
            "note": f"Recorded acquisition elapsed time is {elapsed_days} day(s); 540+ days maps to maximum prototype pressure.",
        },
        {
            "key": "case_scale_complexity",
            "label": "Case scale / affected population",
            "score": scale_complexity,
            "weight": 0.10,
            "note": f"Prototype complexity uses {land_area:.1f} land-area units and {affected_families} affected families; capped for ranking stability.",
        },
    ]
    score = round(sum(float(d["score"]) * float(d["weight"]) for d in drivers))
    if score < 30:
        label = "LOW"
    elif score < 50:
        label = "MODERATE"
    elif score < 70:
        label = "HIGH"
    else:
        label = "CRITICAL"

    return AcquisitionRiskSnapshot(
        score=score,
        label=label,
        current_stage=str(_value(project, "acquisition_stage", overrides) or "UNKNOWN"),
        stage_attention=_stage_attention(project, friction.dominant_blocker, overrides),
        drivers=drivers,
        methodology=(
            "LandGuard Acquisition Delay Risk Index: a transparent land-acquisition-specific decision-support index using "
            "50% recorded acquisition friction, 25% readiness gap, 15% elapsed-acquisition pressure and 10% case-scale "
            "complexity. It directly uses land-acquisition indicators, but it is NOT a trained probability, statutory score, "
            "or government standard. The PAIMANA ML schedule signal is shown separately."
        ),
    )
