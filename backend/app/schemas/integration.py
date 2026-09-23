from pydantic import BaseModel, Field

from app.schemas.project import ProjectWrite


class BulkProjectImportRequest(BaseModel):
    source_system: str = Field(min_length=2, max_length=80)
    dry_run: bool = False
    projects: list[ProjectWrite] = Field(min_length=1, max_length=500)


class BulkProjectImportIssue(BaseModel):
    project_id: str
    detail: str


class BulkProjectImportResult(BaseModel):
    source_system: str
    dry_run: bool
    received: int
    created: int
    updated: int
    rejected: int
    issues: list[BulkProjectImportIssue] = []
