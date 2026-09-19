import asyncio
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.projects import router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.notices import router as notices_router
from app.api.routes.auth import router as auth_router
from app.api.routes.gis import router as gis_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.pipeline import router as pipeline_router
from app.core.config import settings
from app.core.security import current_user
from app.services.identity_service import IdentityError
from app.db.session import get_db

app = FastAPI(title="LandGuard AI", version="0.3.0", description="Predictive land-acquisition delay intelligence prototype with GIS, authenticated decision support, and an explicitly labelled model pipeline.")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-LandGuard-Request"])
app.include_router(router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(dashboard_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(notices_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(auth_router, prefix="/api/v1")
app.include_router(gis_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(intelligence_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(alerts_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(pipeline_router, prefix="/api/v1")


@app.middleware("http")
async def protect_requests(request, call_next):
    if request.url.path.startswith("/api/v1"):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if request.headers.get("x-landguard-request") != "1" or (origin and origin not in settings.allowed_origins):
                return JSONResponse(status_code=403, content={"detail": "Request origin could not be verified."})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    return await call_next(request)


@app.exception_handler(IdentityError)
async def identity_error(request, exc):
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "detail": exc.message})


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logging.getLogger(__name__).exception("Database operation failed", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable. Check database configuration and initialization."})


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    from app.services.intelligence_service import model_status
    status = model_status()
    return {"status": "ok", "database": "connected", "model_status": "available" if status.available else "not_loaded", "model_disclaimer": status.disclaimer}


_pipeline_task = None


async def _pipeline_monitor_loop():
    from app.services.paimana_monitor_service import check_and_update
    await asyncio.sleep(settings.paimana_startup_delay_seconds)
    while True:
        try:
            await asyncio.to_thread(check_and_update)
        except Exception:
            logging.getLogger(__name__).exception("PAIMANA automatic pipeline check failed")
        await asyncio.sleep(settings.paimana_check_interval_hours * 3600)


@app.on_event("startup")
async def start_paimana_monitor():
    global _pipeline_task
    if settings.paimana_auto_monitor_enabled and _pipeline_task is None:
        _pipeline_task = asyncio.create_task(_pipeline_monitor_loop())


@app.on_event("shutdown")
async def stop_paimana_monitor():
    global _pipeline_task
    if _pipeline_task is not None:
        _pipeline_task.cancel()
        try:
            await _pipeline_task
        except asyncio.CancelledError:
            pass
        _pipeline_task = None
