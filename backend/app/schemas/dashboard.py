from typing import Literal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_projects: int
    pending_approvals: int
    projects_with_legal_disputes: int
    avg_compensation_pct: float | None
    illustrative_projects: int
    user_entered_projects: int
    high_risk: None = None
    medium_risk: None = None
    low_risk: None = None
    model_status: str = "See /api/v1/model/status for trained-model availability."


class DistrictSummary(BaseModel):
    state: str
    district: str
    project_count: int
    avg_compensation_pct: float
    avg_possession_pct: float
    pending_approvals: int
    legal_disputes: int
    projects_with_pending_approvals: int
    projects_with_legal_disputes: int


class StageCount(BaseModel):
    stage: str
    count: int


class OperationalThresholds(BaseModel):
    compensation_below_pct: float
    possession_below_pct: float
    response_above_days: int


class OperationalIndicators(BaseModel):
    label: Literal["Operational indicators"] = "Operational indicators"
    projects_with_legal_disputes: int
    projects_with_pending_approvals: int
    projects_below_compensation_threshold: int
    projects_below_possession_threshold: int
    projects_with_slow_stakeholder_response: int
    thresholds: OperationalThresholds
    interpretation: str = "Prototype thresholds, not ML risk factors. Counts overlap; each indicator counts projects once."
