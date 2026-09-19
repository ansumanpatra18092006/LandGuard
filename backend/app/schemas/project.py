from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Percentage = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, le=2147483647)]


class ProjectType(str, Enum):
    ROAD = "ROAD"
    RAILWAY = "RAILWAY"
    IRRIGATION = "IRRIGATION"
    INDUSTRIAL = "INDUSTRIAL"
    URBAN = "URBAN"


class AcquisitionStage(str, Enum):
    NOTIFICATION = "NOTIFICATION"
    SURVEY = "SURVEY"
    VALUATION = "VALUATION"
    COMPENSATION = "COMPENSATION"
    REHABILITATION = "REHABILITATION"
    POSSESSION = "POSSESSION"
    COMPLETED = "COMPLETED"


class ProjectSortField(str, Enum):
    PROJECT_ID = "project_id"
    PROJECT_NAME = "project_name"
    STATE = "state"
    DISTRICT = "district"
    PROJECT_TYPE = "project_type"
    ACQUISITION_STAGE = "acquisition_stage"
    COMPENSATION_COMPLETION_PCT = "compensation_completion_pct"
    POSSESSION_PCT = "possession_pct"
    REHABILITATION_COMPLETION_PCT = "rehabilitation_completion_pct"
    PENDING_APPROVALS = "pending_approvals"
    LEGAL_DISPUTES = "legal_disputes"
    STAKEHOLDER_RESPONSE_DAYS = "stakeholder_response_days"
    ELAPSED_ACQUISITION_DAYS = "elapsed_acquisition_days"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class ProjectWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", allow_inf_nan=False)
    project_id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    project_name: str = Field(min_length=1, max_length=200)
    project_type: ProjectType
    state: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    land_area: float = Field(ge=0)
    affected_families: Count
    compensation_completion_pct: Percentage
    pending_approvals: Count
    legal_disputes: Count
    possession_pct: Percentage
    rehabilitation_completion_pct: Percentage
    stakeholder_response_days: Count
    elapsed_acquisition_days: Count
    acquisition_stage: AcquisitionStage
    original_cost_crore: float | None = Field(default=None, ge=0)
    expenditure_crore: float | None = Field(default=None, ge=0)
    original_end_date: date | None = None


class ProjectRead(ProjectWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data_source: Literal["ILLUSTRATIVE", "USER_ENTERED"]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def explicit_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class ProjectPage(BaseModel):
    items: list[ProjectRead]
    total: int
    page: int
    page_size: int
