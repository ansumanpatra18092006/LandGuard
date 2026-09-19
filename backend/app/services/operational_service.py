from enum import Enum

from app.core.config import settings
from app.models.project import Project


class OperationalIndicator(str, Enum):
    PENDING_APPROVALS = "pending_approvals"
    LEGAL_DISPUTES = "legal_disputes"
    COMPENSATION_LAG = "compensation_lag"
    POSSESSION_LAG = "possession_lag"
    SLOW_RESPONSE = "slow_response"


def indicator_conditions():
    """Shared conditions for counts and drill-downs; prototype rules only."""
    return {
        "pending_approvals": Project.pending_approvals > 0,
        "legal_disputes": Project.legal_disputes > 0,
        "compensation_lag": Project.compensation_completion_pct < settings.compensation_threshold_pct,
        "possession_lag": Project.possession_pct < settings.possession_threshold_pct,
        "slow_response": Project.stakeholder_response_days > settings.slow_response_days,
    }
