from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project


def get_project(db: Session, project_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_id == project_id))
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def save_project(db: Session, project: Project) -> Project:
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Project identifier already exists or a data constraint was violated") from None
    db.refresh(project)
    return project
