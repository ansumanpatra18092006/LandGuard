from typing import Literal
from pydantic import BaseModel, Field


class FactorContribution(BaseModel):
    feature: str
    display_name: str
    contribution: float
    direction: Literal["increases_risk", "reduces_risk"]


class Recommendation(BaseModel):
    factor: str
    action: str
    rationale: str


class SimilarHistoricalCase(BaseModel):
    project_code: str
    snapshot_month: str
    sector_name: str
    similarity_pct: int = Field(ge=0, le=100)
    same_sector: bool
    original_cost_crore: float | None = None
    expenditure_to_original_cost_pct: float | None = None
    days_to_original_deadline: int | None = None
    slipped_within_3_months: bool


class FrictionComponent(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    note: str


class FrictionResult(BaseModel):
    score: int = Field(ge=0, le=100)
    label: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    dominant_blocker: str
    components: list[FrictionComponent]
    methodology: str




class AcquisitionRiskDriver(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    note: str


class AcquisitionDelayRisk(BaseModel):
    score: int = Field(ge=0, le=100)
    label: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    current_stage: str
    stage_attention: str
    drivers: list[AcquisitionRiskDriver]
    methodology: str


class ScenarioRequest(BaseModel):
    expenditure_to_original_cost_pct: float = Field(ge=0, le=150)
    days_to_original_deadline: int | None = Field(default=None, ge=-730, le=1460)
    clear_pending_approvals: bool = False
    resolve_legal_disputes: bool = False
    compensation_target_pct: float | None = Field(default=None, ge=0, le=100)
    possession_target_pct: float | None = Field(default=None, ge=0, le=100)
    rehabilitation_target_pct: float | None = Field(default=None, ge=0, le=100)
    stakeholder_response_target_days: int | None = Field(default=None, ge=0, le=365)


class DelayOutlook(BaseModel):
    expected_extension_days: int = Field(ge=0)
    likely_range_low_days: int = Field(ge=0)
    likely_range_high_days: int = Field(ge=0)
    expected_delay_exposure_days: int = Field(ge=0)
    severity: Literal["MINOR", "SIGNIFICANT", "SEVERE", "CRITICAL"]
    model_name: str | None = None
    conditional_note: str


class ScenarioResult(BaseModel):
    base_probability: float = Field(ge=0, le=1)
    scenario_probability: float = Field(ge=0, le=1)
    probability_change: float = Field(ge=-1, le=1)
    base_risk_category: Literal["LOW", "MEDIUM", "HIGH"]
    scenario_risk_category: Literal["LOW", "MEDIUM", "HIGH"]
    base_alert: bool
    scenario_alert: bool
    scenario_expenditure_to_original_cost_pct: float
    scenario_days_to_original_deadline: int
    base_delay_outlook: DelayOutlook | None = None
    scenario_delay_outlook: DelayOutlook | None = None
    base_friction: FrictionResult
    scenario_friction: FrictionResult
    base_acquisition_delay_risk: AcquisitionDelayRisk
    scenario_acquisition_delay_risk: AcquisitionDelayRisk
    base_readiness_score: int = Field(ge=0, le=100)
    scenario_readiness_score: int = Field(ge=0, le=100)
    base_priority_score: int = Field(ge=0, le=100)
    scenario_priority_score: int = Field(ge=0, le=100)
    base_priority_category: Literal["ROUTINE", "WATCH", "HIGH", "CRITICAL"]
    scenario_priority_category: Literal["ROUTINE", "WATCH", "HIGH", "CRITICAL"]
    note: str
    operational_note: str


class ModelMetadata(BaseModel):
    available: bool
    model_name: str | None = None
    training_data_kind: str | None = None
    explanation_method: str | None = None
    calibration_method: str | None = None
    probability_kind: str | None = None
    probability_threshold: float | None = None
    data_period: str | None = None
    target_definition: str | None = None
    test_split: str | None = None
    model_role: str | None = None
    land_acquisition_features_used: bool = False
    operational_lane_note: str | None = None
    validation_caveat: str | None = None
    disclaimer: str


class PredictionResult(BaseModel):
    project_id: str
    delay_probability: float = Field(ge=0, le=1)
    raw_probability: float = Field(ge=0, le=1)
    risk_score: int = Field(ge=0, le=100)
    risk_category: Literal["LOW", "MEDIUM", "HIGH"]
    predicted_delay_indicator: bool
    delay_outlook: DelayOutlook | None = None
    acquisition_friction: FrictionResult
    acquisition_delay_risk: AcquisitionDelayRisk
    acquisition_readiness_score: int = Field(ge=0, le=100)
    intervention_priority_score: int = Field(ge=0, le=100)
    intervention_priority_category: Literal["ROUTINE", "WATCH", "HIGH", "CRITICAL"]
    factors: list[FactorContribution]
    similar_cases: list[SimilarHistoricalCase] = []
    recommendations: list[Recommendation]
    metadata: ModelMetadata


class ModelStatus(BaseModel):
    available: bool
    model_name: str | None = None
    training_data_kind: str | None = None
    metrics: dict[str, float] | None = None
    data_period: str | None = None
    target_definition: str | None = None
    test_split: str | None = None
    calibration_method: str | None = None
    probability_threshold: float | None = None
    disclaimer: str


class RiskPulseProject(BaseModel):
    project_id: str
    project_name: str
    state: str
    district: str
    delay_probability: float = Field(ge=0, le=1)
    risk_category: Literal["LOW", "MEDIUM", "HIGH"]
    slip_alert: bool
    operational_issue_count: int = Field(ge=0)
    expected_extension_days: int | None = Field(default=None, ge=0)
    expected_delay_exposure_days: int | None = Field(default=None, ge=0)
    impact_severity: Literal["MINOR", "SIGNIFICANT", "SEVERE", "CRITICAL"] | None = None
    primary_bottleneck: str | None = None
    suggested_action: str | None = None
    acquisition_readiness_score: int | None = Field(default=None, ge=0, le=100)
    acquisition_readiness_label: Literal["BLOCKED", "CONSTRAINED", "READY"] | None = None
    acquisition_friction_score: int | None = Field(default=None, ge=0, le=100)
    acquisition_friction_label: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"] | None = None
    acquisition_delay_risk_score: int | None = Field(default=None, ge=0, le=100)
    acquisition_delay_risk_label: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"] | None = None
    intervention_priority_score: int | None = Field(default=None, ge=0, le=100)
    intervention_priority_category: Literal["ROUTINE", "WATCH", "HIGH", "CRITICAL"] | None = None


class RiskPulseResponse(BaseModel):
    model_available: bool
    probability_threshold: float | None = None
    scored_projects: int = Field(ge=0)
    unscored_projects: int = Field(ge=0)
    high_risk: int = Field(ge=0)
    medium_risk: int = Field(ge=0)
    low_risk: int = Field(ge=0)
    intervention_candidates: int = Field(ge=0)
    critical_priority: int = Field(default=0, ge=0)
    high_priority: int = Field(default=0, ge=0)
    average_friction_score: int = Field(default=0, ge=0, le=100)
    average_acquisition_delay_risk_score: int = Field(default=0, ge=0, le=100)
    total_expected_delay_exposure_days: int = Field(default=0, ge=0)
    projects: list[RiskPulseProject] = []
