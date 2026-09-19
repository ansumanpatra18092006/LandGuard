from typing import Literal
from pydantic import BaseModel, Field


class ReadinessComponent(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    note: str


class ReadinessResult(BaseModel):
    project_id: str
    readiness_score: int = Field(ge=0, le=100)
    readiness_label: Literal["BLOCKED", "CONSTRAINED", "READY"]
    primary_blocker: str
    next_milestone: str
    handover_readiness: Literal["BLOCKED", "CONSTRAINED", "READY"]
    components: list[ReadinessComponent]
    methodology: str
