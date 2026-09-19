from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InterventionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    action: str = Field(min_length=3, max_length=220)
    assigned_to: str = Field(min_length=2, max_length=160)
    due_date: date
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    source: Literal["OFFICER", "RECOMMENDATION", "WAR_ROOM"] = "OFFICER"


class InterventionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    assigned_to: str | None = Field(default=None, min_length=2, max_length=160)
    due_date: date | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"] | None = None
    resolution_note: str | None = Field(default=None, max_length=2000)


class InterventionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    actor: str
    detail: str
    created_at: datetime


class InterventionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: str
    action: str
    assigned_to: str
    due_date: date
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"]
    source: str
    resolution_note: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    overdue: bool = False
    events: list[InterventionEventRead] = []


class InterventionSummary(BaseModel):
    open_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    in_progress_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
