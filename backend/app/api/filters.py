from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy import or_

from app.models.project import Project
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, scope_projects
from app.schemas.project import AcquisitionStage, ProjectType
from app.services.operational_service import OperationalIndicator, indicator_conditions


@dataclass
class ProjectFilters:
    search: str = ""
    state: str | None = None
    district: str | None = None
    project_type: ProjectType | None = None
    acquisition_stage: AcquisitionStage | None = None
    indicator: OperationalIndicator | None = None

    user: dict | None = None

    def apply(self, query):
        if self.user is not None:
            query = scope_projects(query, self.user)
        if self.indicator is not None:
            query = query.where(indicator_conditions()[self.indicator])
        for field in ("state", "district", "project_type", "acquisition_stage"):
            value = getattr(self, field)
            if value is not None:
                query = query.where(getattr(Project, field) == value)
        if self.search.strip():
            query = query.where(or_(
                Project.project_name.icontains(self.search.strip(), autoescape=True),
                Project.project_id.icontains(self.search.strip(), autoescape=True),
            ))
        return query


def project_filters(search: str = Query("", max_length=200),
                    state: str | None = Query(None, max_length=100),
                    district: str | None = Query(None, max_length=100),
                    project_type: ProjectType | None = None,
                    acquisition_stage: AcquisitionStage | None = None,
                    indicator: OperationalIndicator | None = None,
                    user=Depends(require_roles(*OPERATIONAL_ROLES))) -> ProjectFilters:
    return ProjectFilters(search, state, district, project_type, acquisition_stage, indicator, user)


Filters = Annotated[ProjectFilters, Depends(project_filters)]
