from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProjectAuditItem(BaseModel):
    id: int
    event_type: str
    actor_id: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    source: str
    changed_fields: list[str] = []
    detail: str
    created_at: datetime


class ProjectSnapshotItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    acquisition_stage: str
    compensation_completion_pct: float
    pending_approvals: int
    legal_disputes: int
    possession_pct: float
    rehabilitation_completion_pct: float
    stakeholder_response_days: int
    elapsed_acquisition_days: int
    acquisition_risk_score: int | None = Field(default=None, ge=0, le=100)
    delay_probability: float | None = Field(default=None, ge=0, le=1)
    captured_at: datetime


class ProjectHistoryResponse(BaseModel):
    project_id: str
    events: list[ProjectAuditItem]
    snapshots: list[ProjectSnapshotItem]
