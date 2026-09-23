from __future__ import annotations

from app.models.project import Project

STAGES = ["NOTIFICATION", "SURVEY", "VALUATION", "COMPENSATION", "REHABILITATION", "POSSESSION", "COMPLETED"]


def _clamp(value: float) -> int:
    return round(max(0.0, min(100.0, value)))


def _label(score: int) -> str:
    if score < 30:
        return "LOW"
    if score < 50:
        return "MODERATE"
    if score < 70:
        return "HIGH"
    return "CRITICAL"


def _status(current: str, stage: str) -> str:
    try:
        current_index = STAGES.index(current)
        stage_index = STAGES.index(stage)
    except ValueError:
        return "UPCOMING"
    if stage_index < current_index:
        return "PASSED"
    if stage_index == current_index:
        return "CURRENT"
    return "UPCOMING"


def stage_delay_outlook(project: Project) -> list[dict]:
    """Transparent stage-by-stage screening outlook.

    These are deliberately not labelled calibrated probabilities. The SIH problem
    asks for stage-wise delay prediction, but the current public training sources do
    not provide validated labels for every acquisition stage. LandGuard therefore
    exposes a stage-wise screening likelihood derived from the recorded acquisition
    indicators until authoritative stage-labelled history is connected.
    """
    approvals = min(100.0, float(project.pending_approvals or 0) / 5.0 * 100.0)
    disputes = min(100.0, float(project.legal_disputes or 0) / 3.0 * 100.0)
    response = min(100.0, float(project.stakeholder_response_days or 0) / 45.0 * 100.0)
    elapsed = min(100.0, float(project.elapsed_acquisition_days or 0) / 540.0 * 100.0)
    scale = min(100.0, ((float(project.land_area or 0) / 250.0 * 100.0) + (float(project.affected_families or 0) / 500.0 * 100.0)) / 2.0)
    compensation_gap = 100.0 - float(project.compensation_completion_pct or 0)
    rehab_gap = 100.0 - float(project.rehabilitation_completion_pct or 0)
    possession_gap = 100.0 - float(project.possession_pct or 0)

    stage_inputs = {
        "NOTIFICATION": [
            ("Pending approvals", approvals, 0.40),
            ("Stakeholder response", response, 0.25),
            ("Legal disputes", disputes, 0.20),
            ("Elapsed acquisition", elapsed, 0.15),
        ],
        "SURVEY": [
            ("Case scale", scale, 0.35),
            ("Stakeholder response", response, 0.25),
            ("Legal disputes", disputes, 0.25),
            ("Pending approvals", approvals, 0.15),
        ],
        "VALUATION": [
            ("Case scale", scale, 0.30),
            ("Legal disputes", disputes, 0.30),
            ("Stakeholder response", response, 0.20),
            ("Elapsed acquisition", elapsed, 0.20),
        ],
        "COMPENSATION": [
            ("Compensation gap", compensation_gap, 0.45),
            ("Legal disputes", disputes, 0.25),
            ("Affected-case scale", scale, 0.15),
            ("Stakeholder response", response, 0.15),
        ],
        "REHABILITATION": [
            ("R&R gap", rehab_gap, 0.45),
            ("Affected-case scale", scale, 0.25),
            ("Stakeholder response", response, 0.20),
            ("Legal disputes", disputes, 0.10),
        ],
        "POSSESSION": [
            ("Possession gap", possession_gap, 0.45),
            ("Compensation gap", compensation_gap, 0.20),
            ("Legal disputes", disputes, 0.20),
            ("Pending approvals", approvals, 0.15),
        ],
    }

    current = str(project.acquisition_stage or "NOTIFICATION").upper()
    rows = []
    for stage in STAGES:
        status = _status(current, stage)
        if stage == "COMPLETED":
            score = 0 if current == "COMPLETED" else _clamp((compensation_gap + rehab_gap + possession_gap) / 3.0)
            drivers = ["Compensation completion", "Rehabilitation completion", "Possession completion"]
        else:
            weighted = stage_inputs[stage]
            score = _clamp(sum(value * weight for _, value, weight in weighted))
            drivers = [name for name, value, _ in sorted(weighted, key=lambda item: item[1] * item[2], reverse=True)[:2] if value > 0]
        rows.append({
            "stage": stage,
            "status": status,
            "screening_score": score,
            "risk_label": _label(score),
            "top_drivers": drivers,
            "interpretation": (
                "Transparent stage-screening estimate from recorded acquisition indicators; "
                "not a calibrated stage-specific ML probability."
            ),
        })
    return rows
