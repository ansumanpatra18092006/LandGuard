from fastapi import APIRouter, Depends, HTTPException

from app.core.security import current_user
from app.schemas.pipeline import PipelineRunResult, PipelineStatus
from app.services.paimana_monitor_service import check_and_update, pipeline_status

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _system_admin(user=Depends(current_user)):
    if user.get("role") != "SYSTEM_ADMIN":
        raise HTTPException(status_code=403, detail="System administrator access required")
    return user


@router.get("/status", response_model=PipelineStatus)
def status(_=Depends(_system_admin)):
    return pipeline_status()


@router.post("/check", response_model=PipelineRunResult)
def check_now(_=Depends(_system_admin)):
    return {**check_and_update(), "checked_now": True}
