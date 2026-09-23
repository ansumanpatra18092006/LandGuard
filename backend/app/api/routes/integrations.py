from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import OPERATIONAL_ROLES, assert_project_access
from app.core.security import require_roles
from app.db.session import get_db
from app.models.project import Project
from app.schemas.integration import BulkProjectImportRequest, BulkProjectImportResult
from app.services.intervention_automation_service import evaluate_project
from app.services.project_history_service import project_state, record_audit, record_snapshot

router = APIRouter(prefix="/integrations", tags=["external integrations"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/capabilities")
def capabilities(_user=Depends(require_roles(*OPERATIONAL_ROLES))):
    return {
        "project_bulk_upsert": True,
        "max_projects_per_request": 500,
        "cadastral_geojson_import": "/api/v1/gis/ownership/import",
        "authentication": "LandGuard authenticated operational session in this prototype; production service credentials/API gateway are deployment concerns.",
        "supported_project_fields": [
            "project type", "state", "district", "location", "land area", "affected families",
            "compensation", "approvals", "legal disputes", "possession", "rehabilitation",
            "stakeholder response", "elapsed acquisition days", "acquisition stage", "cost/expenditure/deadline",
        ],
    }


@router.post("/projects/bulk-upsert", response_model=BulkProjectImportResult)
def bulk_upsert_projects(
    payload: BulkProjectImportRequest,
    db: Database,
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    created = updated = rejected = 0
    issues = []
    source = f"INTEGRATION:{payload.source_system.strip()}"[:80]

    for item in payload.projects:
        data = item.model_dump()
        project_id = data["project_id"]
        try:
            existing = db.scalar(select(Project).where(Project.project_id == project_id))
            candidate = Project(**data)
            assert_project_access(candidate, user)
            if existing is not None:
                assert_project_access(existing, user)
                before = project_state(existing)
                if not payload.dry_run:
                    for field, value in data.items():
                        setattr(existing, field, value)
                    existing.data_source = "INTEGRATED"
                    db.flush()
                    record_snapshot(db, existing)
                    record_audit(
                        db, project_id=project_id, event_type="INTEGRATION_UPDATED", user=user,
                        before=before, after=project_state(existing), source=source,
                        detail=f"Project synchronized from {payload.source_system}.",
                    )
                    evaluate_project(db, existing)
                updated += 1
            else:
                if not payload.dry_run:
                    candidate.data_source = "INTEGRATED"
                    db.add(candidate)
                    db.flush()
                    record_snapshot(db, candidate)
                    record_audit(
                        db, project_id=project_id, event_type="INTEGRATION_CREATED", user=user,
                        after=project_state(candidate), source=source,
                        detail=f"Project imported from {payload.source_system}.",
                    )
                    evaluate_project(db, candidate)
                created += 1
        except Exception as exc:
            db.rollback()
            rejected += 1
            issues.append({"project_id": project_id, "detail": str(exc)[:300]})

    if payload.dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "source_system": payload.source_system,
        "dry_run": payload.dry_run,
        "received": len(payload.projects),
        "created": created,
        "updated": updated,
        "rejected": rejected,
        "issues": issues,
    }
