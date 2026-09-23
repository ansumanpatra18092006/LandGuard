import asyncio
import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
from app.api.routes.interventions import router as interventions_router, summary_router as intervention_summary_router
from app.api.routes.readiness import router as readiness_router
from app.api.routes.automation import router as automation_router
from app.api.routes.route_analysis import router as route_analysis_router
from app.api.routes.integrations import router as integrations_router
from app.core.config import settings
from app.core.security import current_user
from app.services.identity_service import IdentityError
from app.db.session import get_db, SessionLocal

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
app.include_router(interventions_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(intervention_summary_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(readiness_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(automation_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(route_analysis_router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(integrations_router, prefix="/api/v1", dependencies=[Depends(current_user)])


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


_automation_task = None


async def _intervention_automation_loop():
    from app.services.intervention_automation_service import evaluate_all_projects
    await asyncio.sleep(settings.intervention_automation_startup_delay_seconds)
    while True:
        try:
            def run_once():
                with SessionLocal() as db:
                    evaluate_all_projects(db)
            await asyncio.to_thread(run_once)
        except Exception:
            logging.getLogger(__name__).exception("Intervention automation cycle failed")
        await asyncio.sleep(settings.intervention_automation_interval_minutes * 60)


@app.on_event("startup")
async def start_intervention_automation():
    global _automation_task
    if settings.intervention_automation_enabled and _automation_task is None:
        _automation_task = asyncio.create_task(_intervention_automation_loop())


@app.on_event("shutdown")
async def stop_intervention_automation():
    global _automation_task
    if _automation_task is not None:
        _automation_task.cancel()
        try:
            await _automation_task
        except asyncio.CancelledError:
            pass
        _automation_task = None


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

# Production single-origin deployment: when the React build exists, serve it from
# the same FastAPI process. This keeps session cookies and CSRF origin checks
# same-site while preserving the normal Vite dev workflow when dist/ is absent.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_DIST = _PROJECT_ROOT / "frontend" / "dist"
_FRONTEND_ASSETS = _FRONTEND_DIST / "assets"

if _FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_ASSETS), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    # API paths are intentionally not handled by the SPA fallback. Existing API
    # routes are registered above and therefore match first; unknown /api paths
    # should remain a normal 404 rather than returning index.html.
    if full_path.startswith("api/") or full_path == "api":
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    if not _FRONTEND_DIST.is_dir():
        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend build not found. Run `npm run build` in frontend/."},
        )

    requested = (_FRONTEND_DIST / full_path).resolve()
    try:
        requested.relative_to(_FRONTEND_DIST.resolve())
    except ValueError:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    if full_path and requested.is_file():
        return FileResponse(requested)

    return FileResponse(_FRONTEND_DIST / "index.html")

