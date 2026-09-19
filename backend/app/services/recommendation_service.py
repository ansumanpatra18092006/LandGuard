from app.schemas.intelligence import FactorContribution, Recommendation

MODEL_RULES = {
    "days_to_original_deadline": (
        "Review schedule recovery plan",
        "The model identified the project's position relative to its original completion deadline as an important schedule-slip signal.",
    ),
    "original_deadline_passed": (
        "Initiate immediate schedule review",
        "The original project completion deadline has already passed, which warrants an authorized schedule-recovery review.",
    ),
    "expenditure_to_original_cost_pct": (
        "Review expenditure-to-progress alignment",
        "The model identified expenditure relative to original cost as a schedule-slip signal; officials should compare spending with actual physical and acquisition progress.",
    ),
    "expenditure_crore": (
        "Review expenditure trajectory",
        "Cumulative expenditure contributed to the schedule-risk estimate and should be reviewed against project milestones.",
    ),
}


def recommendations_for(factors: list[FactorContribution], project=None) -> list[Recommendation]:
    output: list[Recommendation] = []
    for factor in factors:
        if factor.direction != "increases_risk" or factor.feature not in MODEL_RULES:
            continue
        action, rationale = MODEL_RULES[factor.feature]
        output.append(Recommendation(factor=factor.display_name, action=action, rationale=rationale))

    # Land-acquisition indicators are operational rules, not PAIMANA model features.
    if project is not None:
        if project.pending_approvals > 0:
            output.append(Recommendation(
                factor="Pending approvals",
                action="Escalate pending approvals",
                rationale="This is a recorded LandGuard operational indicator, separate from the PAIMANA model prediction.",
            ))
        if project.legal_disputes > 0:
            output.append(Recommendation(
                factor="Legal disputes",
                action="Prioritize authorized legal review",
                rationale="This is a recorded land-acquisition operational indicator, not a feature used to train the PAIMANA model.",
            ))
        if project.compensation_completion_pct < 60:
            output.append(Recommendation(
                factor="Compensation progress",
                action="Review pending compensation processing",
                rationale="Low compensation completion is a LandGuard operational indicator and remains separate from the real-data PAIMANA baseline.",
            ))

    if not output:
        output.append(Recommendation(
            factor="No dominant intervention signal",
            action="Continue monitoring",
            rationale="No strong model or recorded operational indicator currently requires a specific prototype recommendation.",
        ))
    return output[:4]
