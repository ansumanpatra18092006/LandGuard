import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["SYSTEM_ADMIN", "STATE_OFFICER", "DISTRICT_OFFICER", "IMPLEMENTING_AGENCY"]
AssignableRole = Literal["STATE_OFFICER", "DISTRICT_OFFICER", "IMPLEMENTING_AGENCY"]

class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@,<>]+@[^\s@,<>]+\.[^\s@,<>]+", value):
            raise ValueError("Enter a valid email address")
        return value

class LoginRequest(EmailRequest):
    password: str = Field(min_length=1, max_length=128)

class AuthUser(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: Role
    status: Literal["invited", "active", "disabled"]
    state: str | None = None
    district: str | None = None
    project_ids: list[str] = Field(default_factory=list)

class SessionResponse(BaseModel):
    user: AuthUser

class SessionProbeResponse(BaseModel):
    authenticated: bool
    user: AuthUser | None = None

class InvitationRequest(EmailRequest):
    display_name: str = Field(min_length=2, max_length=100)
    role: AssignableRole
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    project_ids: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def assigned_scope(self):
        self.display_name = self.display_name.strip()
        if len(self.display_name) < 2:
            raise ValueError("Enter a name")
        self.state = (self.state or "").strip() or None
        self.district = (self.district or "").strip() or None
        self.project_ids = list(dict.fromkeys(p.strip() for p in self.project_ids if p.strip()))
        if any(len(p) > 100 for p in self.project_ids):
            raise ValueError("Project ID is too long")
        if self.role in ("STATE_OFFICER", "DISTRICT_OFFICER") and not self.state:
            raise ValueError("Assign a state")
        if self.role == "DISTRICT_OFFICER" and not self.district:
            raise ValueError("Assign a district")
        if self.role == "IMPLEMENTING_AGENCY" and not self.project_ids:
            raise ValueError("Assign at least one project ID")
        return self

class InvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token_hash: str = Field(min_length=20, max_length=512, pattern=r"^[A-Za-z0-9_\-]+$")
    type: Literal["invite", "recovery"]
    password: str = Field(min_length=12, max_length=128)

class UserStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["active", "disabled"]

class ManagedUser(AuthUser):
    invitation_delivery: str = "not_sent"
    invited_at: str | None = None
    created_at: str | None = None

class AuditEvent(BaseModel):
    id: int
    actor_id: UUID | None = None
    subject_id: UUID | None = None
    event: str
    created_at: str
