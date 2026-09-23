from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, assert_project_access, scope_projects
from app.db.session import get_db
from app.schemas.intelligence import ModelStatus, PredictionResult, ScenarioRequest, ScenarioResult, RiskPulseResponse, BhoomiRashiSignal, StageDelayOutlook
from app.services.intelligence_service import model_status, predict, scenario, portfolio_risk_pulse
from app.services.project_service import get_project
from app.services.bhoomirashi_intelligence_service import predict_bhoomirashi
from app.services.stage_outlook_service import stage_delay_outlook
from app.models.project import Project

router = APIRouter(tags=["intelligence"])


@router.get("/model/status", response_model=ModelStatus)
def status(_user=Depends(require_roles(*OPERATIONAL_ROLES))):
    return model_status()




@router.get("/risk-pulse", response_model=RiskPulseResponse)
def risk_pulse(
    db: Annotated[Session, Depends(get_db)],
    state: str | None = Query(None, max_length=100),
    district: str | None = Query(None, max_length=100),
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    query = scope_projects(select(Project), user)
    if state:
        query = query.where(Project.state == state)
    if district:
        query = query.where(Project.district == district)
    projects = db.scalars(query.order_by(Project.project_id)).all()
    return portfolio_risk_pulse(list(projects))




@router.get("/projects/{project_id}/stage-outlook", response_model=list[StageDelayOutlook])
def project_stage_outlook(project_id: str, db: Annotated[Session, Depends(get_db)], _user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, _user)
    return stage_delay_outlook(project)


@router.get("/projects/{project_id}/bhoomirashi-predict", response_model=BhoomiRashiSignal)
def bhoomirashi_prediction(project_id: str, db: Annotated[Session, Depends(get_db)], _user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, _user)
    return predict_bhoomirashi(project)


@router.post("/projects/{project_id}/predict", response_model=PredictionResult)
def project_prediction(project_id: str, db: Annotated[Session, Depends(get_db)], _user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, _user)
    try:
        return predict(project)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/projects/{project_id}/scenario", response_model=ScenarioResult)
def project_scenario(payload: ScenarioRequest, project_id: str, db: Annotated[Session, Depends(get_db)], _user=Depends(require_roles(*OPERATIONAL_ROLES))):
    project = get_project(db, project_id); assert_project_access(project, _user)
    try:
        return scenario(
            project, payload.expenditure_to_original_cost_pct, payload.days_to_original_deadline,
            clear_pending_approvals=payload.clear_pending_approvals,
            resolve_legal_disputes=payload.resolve_legal_disputes,
            compensation_target_pct=payload.compensation_target_pct,
            possession_target_pct=payload.possession_target_pct,
            rehabilitation_target_pct=payload.rehabilitation_target_pct,
            stakeholder_response_target_days=payload.stakeholder_response_target_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
