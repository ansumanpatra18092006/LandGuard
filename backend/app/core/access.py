from fastapi import HTTPException
from sqlalchemy import false

from app.models.project import Project

SYSTEM_ADMIN_ROLE = "SYSTEM_ADMIN"
OPERATIONAL_ROLES = ("STATE_OFFICER", "DISTRICT_OFFICER", "IMPLEMENTING_AGENCY")


def scope_projects(query, user):
    role = user.get("role")
    if role == "STATE_OFFICER" and user.get("state"):
        return query.where(Project.state == user["state"])
    if role == "DISTRICT_OFFICER" and user.get("state") and user.get("district"):
        return query.where(Project.state == user["state"], Project.district == user["district"])
    if role == "IMPLEMENTING_AGENCY":
        return query.where(Project.project_id.in_(user.get("project_ids", [])))
    return query.where(false())


def assert_project_access(project, user):
    role = user.get("role")
    permitted = (
        role == "STATE_OFFICER" and user.get("state") == project.state
        or role == "DISTRICT_OFFICER" and user.get("state") == project.state and user.get("district") == project.district
        or role == "IMPLEMENTING_AGENCY" and project.project_id in user.get("project_ids", [])
    )
    if not permitted:
        raise HTTPException(404, "Project not found")
