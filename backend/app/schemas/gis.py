from pydantic import BaseModel, ConfigDict


class MapProject(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    project_name: str
    state: str
    district: str
    latitude: float
    longitude: float
    acquisition_stage: str
    pending_approvals: int
    legal_disputes: int
    compensation_completion_pct: float
    possession_pct: float
    rehabilitation_completion_pct: float
    project_type: str
    distance_km: float | None = None
    delay_probability: float | None = None
    risk_category: str | None = None
    slip_alert: bool | None = None
