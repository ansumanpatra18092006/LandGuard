from fastapi import HTTPException
from sqlalchemy import false, func

from app.models.project import Project

SYSTEM_ADMIN_ROLE = "SYSTEM_ADMIN"
OPERATIONAL_ROLES = ("STATE_OFFICER", "DISTRICT_OFFICER", "IMPLEMENTING_AGENCY")


def _norm(value):
    return (value or "").strip().casefold()


def _same(a, b):
    return _norm(a) == _norm(b)


def _project_in_scope(project, user):
    role = user.get("role")
    return (
        role == "STATE_OFFICER" and _same(user.get("state"), project.state)
        or role == "DISTRICT_OFFICER"
        and _same(user.get("state"), project.state)
        and _same(user.get("district"), project.district)
        or role == "IMPLEMENTING_AGENCY" and project.project_id in user.get("project_ids", [])
    )


def scope_projects(query, user):
    role = user.get("role")
    if role == "STATE_OFFICER" and user.get("state"):
        return query.where(func.lower(func.trim(Project.state)) == _norm(user["state"]))
    if role == "DISTRICT_OFFICER" and user.get("state") and user.get("district"):
        return query.where(
            func.lower(func.trim(Project.state)) == _norm(user["state"]),
            func.lower(func.trim(Project.district)) == _norm(user["district"]),
        )
    if role == "IMPLEMENTING_AGENCY":
        return query.where(Project.project_id.in_(user.get("project_ids", [])))
    return query.where(false())


def assert_project_access(project, user):
    """Protect reads/updates/deletes without leaking records outside scope."""
    if not _project_in_scope(project, user):
        raise HTTPException(404, "Project not found")

