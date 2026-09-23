from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.filters import ProjectFilters
from app.core.config import settings
from app.models.project import Project as P
from app.models.project_audit import ProjectSnapshot
from app.services.operational_service import indicator_conditions
from app.services.acquisition_risk_service import acquisition_delay_risk_for


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
        count_where(P.data_source == "INTEGRATED").label("integrated_projects"),
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


def delay_trends(db: Session, filters: ProjectFilters, *, group_by: str = "district", days: int = 365) -> list[dict]:
    project_ids = list(db.scalars(filters.apply(select(P.project_id))).all())
    if not project_ids:
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    snapshots = list(db.scalars(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id.in_(project_ids), ProjectSnapshot.captured_at >= since)
        .order_by(ProjectSnapshot.captured_at, ProjectSnapshot.project_id)
    ).all())
    buckets = defaultdict(list)
    for row in snapshots:
        captured = row.captured_at
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        period = captured.date().isoformat()
        label = row.state if group_by == "state" else f"{row.district}, {row.state}"
        buckets[(period, label)].append(row)
    output = []
    for (period, label), rows in sorted(buckets.items()):
        risk_values = [
            r.acquisition_risk_score if r.acquisition_risk_score is not None else acquisition_delay_risk_for(r).score
            for r in rows
        ]
        delay_values = [r.delay_probability for r in rows if r.delay_probability is not None]
        output.append({
            "period": period,
            "group_label": label,
            "avg_acquisition_risk_score": round(sum(risk_values) / len(risk_values), 1) if risk_values else 0.0,
            "avg_delay_probability": round(sum(delay_values) / len(delay_values), 4) if delay_values else None,
            "project_count": len({r.project_id for r in rows}),
        })
    return output
