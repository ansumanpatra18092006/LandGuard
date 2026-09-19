from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.filters import ProjectFilters
from app.core.config import settings
from app.models.project import Project as P
from app.services.operational_service import indicator_conditions


def count_where(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def summary(db: Session, filters: ProjectFilters) -> dict:
    row = db.execute(filters.apply(select(
        func.count(P.id).label("total_projects"),
        func.coalesce(func.sum(P.pending_approvals), 0).label("pending_approvals"),
        count_where(P.legal_disputes > 0).label("projects_with_legal_disputes"),
        func.avg(P.compensation_completion_pct).label("avg_compensation_pct"),
        count_where(P.data_source == "ILLUSTRATIVE").label("illustrative_projects"),
        count_where(P.data_source == "USER_ENTERED").label("user_entered_projects"),
    ))).mappings().one()
    result = dict(row)
    if result["avg_compensation_pct"] is not None:
        result["avg_compensation_pct"] = round(result["avg_compensation_pct"], 2)
    return result


def districts(db: Session, filters: ProjectFilters) -> list[dict]:
    query = filters.apply(select(
        P.state, P.district, func.count(P.id).label("project_count"),
        func.avg(P.compensation_completion_pct).label("avg_compensation_pct"),
        func.avg(P.possession_pct).label("avg_possession_pct"),
        func.sum(P.pending_approvals).label("pending_approvals"),
        func.sum(P.legal_disputes).label("legal_disputes"),
        count_where(P.pending_approvals > 0).label("projects_with_pending_approvals"),
        count_where(P.legal_disputes > 0).label("projects_with_legal_disputes"),
    )).group_by(P.state, P.district).order_by(P.state, P.district)
    return [{**row, "avg_compensation_pct": round(row["avg_compensation_pct"], 2),
             "avg_possession_pct": round(row["avg_possession_pct"], 2)}
            for row in db.execute(query).mappings()]


def stages(db: Session, filters: ProjectFilters) -> list[dict]:
    query = filters.apply(select(P.acquisition_stage.label("stage"), func.count(P.id).label("count")))
    query = query.group_by(P.acquisition_stage).order_by(P.acquisition_stage)
    return [dict(row) for row in db.execute(query).mappings()]


def operational_indicators(db: Session, filters: ProjectFilters) -> dict:
    conditions = indicator_conditions()
    query = filters.apply(select(
        count_where(conditions["legal_disputes"]).label("projects_with_legal_disputes"),
        count_where(conditions["pending_approvals"]).label("projects_with_pending_approvals"),
        count_where(conditions["compensation_lag"])
        .label("projects_below_compensation_threshold"),
        count_where(conditions["possession_lag"])
        .label("projects_below_possession_threshold"),
        count_where(conditions["slow_response"])
        .label("projects_with_slow_stakeholder_response"),
    ))
    return {**db.execute(query).mappings().one(), "thresholds": {
        "compensation_below_pct": settings.compensation_threshold_pct,
        "possession_below_pct": settings.possession_threshold_pct,
        "response_above_days": settings.slow_response_days,
    }}
