from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.paimana_features import DISPLAY_NAMES, FEATURES, NUMERIC_FEATURES, PROJECT_TYPE_TO_SECTOR, TARGET
from app.models.project import Project
from app.schemas.intelligence import (
    FactorContribution,
    DelayOutlook,
    ModelMetadata,
    ModelStatus,
    PredictionResult,
    ScenarioResult,
    SimilarHistoricalCase,
    RiskPulseProject,
    RiskPulseResponse,
    FrictionResult,
    AcquisitionDelayRisk,
)
from app.services.recommendation_service import recommendations_for
from app.services.readiness_service import readiness_for
from app.services.friction_service import friction_for, intervention_priority
from app.services.acquisition_risk_service import acquisition_delay_risk_for

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "model_artifacts"
PANEL_PATH = ROOT / "data" / "paimana_longitudinal_training.csv"
_MODEL = None
_METADATA = None
_CALIBRATOR = None
_PANEL = None
_DURATION_MODEL = None
_DURATION_METADATA = None


def reset_model_cache():
    global _MODEL, _METADATA, _CALIBRATOR, _PANEL, _DURATION_MODEL, _DURATION_METADATA
    _MODEL = None
    _METADATA = None
    _CALIBRATOR = None
    _PANEL = None
    _DURATION_MODEL = None
    _DURATION_METADATA = None


def _load():
    global _MODEL, _METADATA, _CALIBRATOR, _DURATION_MODEL, _DURATION_METADATA
    model_path = ARTIFACT_DIR / "classifier.joblib"
    meta_path = ARTIFACT_DIR / "metadata.json"
    if not model_path.exists() or not meta_path.exists():
        return None, None, None
    if _MODEL is None:
        _MODEL = joblib.load(model_path)
        _METADATA = json.loads(meta_path.read_text(encoding="utf-8"))
        calibrator_path = ARTIFACT_DIR / "probability_calibrator.joblib"
        _CALIBRATOR = joblib.load(calibrator_path) if calibrator_path.exists() else None
        duration_path = ARTIFACT_DIR / "delay_duration_regressor.joblib"
        duration_meta_path = ARTIFACT_DIR / "duration_metadata.json"
        _DURATION_MODEL = joblib.load(duration_path) if duration_path.exists() else None
        _DURATION_METADATA = json.loads(duration_meta_path.read_text(encoding="utf-8")) if duration_meta_path.exists() else None
    return _MODEL, _METADATA, _CALIBRATOR


def _panel() -> pd.DataFrame | None:
    global _PANEL
    if _PANEL is None and PANEL_PATH.exists():
        _PANEL = pd.read_csv(PANEL_PATH)
    return _PANEL


def model_status() -> ModelStatus:
    _, metadata, calibrator = _load()
    if not metadata:
        return ModelStatus(available=False, disclaimer="No trained model artifact is loaded. Train the PAIMANA longitudinal baseline first.")
    return ModelStatus(
        available=True,
        model_name=metadata.get("model_name"),
        training_data_kind=metadata.get("training_data_kind"),
        metrics=metadata.get("metrics"),
        data_period=metadata.get("data_period"),
        target_definition=metadata.get("target_definition"),
        test_split=metadata.get("test_split"),
        calibration_method=metadata.get("calibration_method") if calibrator is not None else None,
        probability_threshold=metadata.get("probability_threshold"),
        disclaimer=metadata.get("disclaimer", "Prototype model."),
    )


def _frame(project: Project) -> pd.DataFrame:
    missing = [field for field in ("original_cost_crore", "expenditure_crore", "original_end_date") if getattr(project, field, None) is None]
    if missing:
        readable = ", ".join(DISPLAY_NAMES.get(x, x.replace("_", " ")) for x in missing)
        raise ValueError("Prediction baseline is incomplete. Add " + readable + " to this project before running intelligence.")
    if project.original_cost_crore <= 0:
        raise ValueError("Original project cost must be greater than zero before running intelligence.")
    today = datetime.now(timezone.utc).date()
    days_to_deadline = (project.original_end_date - today).days
    ratio = (project.expenditure_crore / project.original_cost_crore) * 100
    sector = PROJECT_TYPE_TO_SECTOR.get(project.project_type, project.project_type)
    row = {
        "sector_name": sector,
        "original_cost_crore": float(project.original_cost_crore),
        "expenditure_crore": float(project.expenditure_crore),
        "days_to_original_deadline": int(days_to_deadline),
        "original_deadline_passed": int(days_to_deadline < 0),
        "expenditure_to_original_cost_pct": float(ratio),
    }
    return pd.DataFrame([row], columns=FEATURES)


def _probabilities(model, calibrator, row: pd.DataFrame) -> tuple[float, float]:
    raw = float(model.predict_proba(row)[0, 1])
    calibrated = float(calibrator.predict_proba(np.array([[raw]]))[0, 1]) if calibrator is not None else raw
    return raw, calibrated


def _risk(probability: float, threshold: float) -> str:
    if probability < 0.30:
        return "LOW"
    if probability < threshold:
        return "MEDIUM"
    return "HIGH"


def _raw_feature(transformed_name: str) -> str:
    name = transformed_name.split("__", 1)[-1]
    for feature in FEATURES:
        if name == feature or name.startswith(feature + "_"):
            return feature
    return name


def _shap_factors(model, row: pd.DataFrame) -> tuple[list[FactorContribution], str]:
    import shap
    pre = model.named_steps["preprocessor"]
    estimator = model.named_steps["model"]
    transformed = pre.transform(row)
    feature_names = list(pre.get_feature_names_out())
    if estimator.__class__.__name__ == "LogisticRegression":
        explainer = shap.LinearExplainer(estimator, transformed)
        values = np.asarray(explainer.shap_values(transformed))
    else:
        explainer = shap.TreeExplainer(estimator)
        values = np.asarray(explainer.shap_values(transformed))
    if values.ndim == 3:
        values = values[:, :, -1]
    values = values.reshape(-1)
    aggregate: dict[str, float] = {}
    for name, value in zip(feature_names, values):
        raw = _raw_feature(name)
        aggregate[raw] = aggregate.get(raw, 0.0) + float(value)
    factors = [
        FactorContribution(feature=f, display_name=DISPLAY_NAMES.get(f, f.replace("_", " ").title()),
                           contribution=round(abs(v), 4), direction="increases_risk" if v > 0 else "reduces_risk")
        for f, v in aggregate.items() if abs(v) >= 0.005
    ]
    return sorted(factors, key=lambda x: x.contribution, reverse=True)[:5], "SHAP local explanation for the PAIMANA schedule-slip baseline, aggregated to project fields."


def _perturbation_factors(model, row: pd.DataFrame, probability: float) -> tuple[list[FactorContribution], str]:
    neutral = {
        "original_cost_crore": row["original_cost_crore"].iloc[0],
        "expenditure_crore": row["original_cost_crore"].iloc[0] * 0.6,
        "days_to_original_deadline": 180,
        "original_deadline_passed": 0,
        "expenditure_to_original_cost_pct": 60.0,
    }
    factors = []
    for feature in NUMERIC_FEATURES:
        altered = row.copy(); altered.loc[0, feature] = neutral[feature]
        changed = float(model.predict_proba(altered)[0, 1])
        contribution = probability - changed
        if abs(contribution) >= 0.01:
            factors.append(FactorContribution(feature=feature, display_name=DISPLAY_NAMES[feature], contribution=round(abs(contribution), 4), direction="increases_risk" if contribution > 0 else "reduces_risk"))
    return sorted(factors, key=lambda x: x.contribution, reverse=True)[:5], "Local probability perturbation fallback (SHAP unavailable for this artifact/runtime)."


def _local_factors(model, row: pd.DataFrame, raw_probability: float) -> tuple[list[FactorContribution], str]:
    try:
        return _shap_factors(model, row)
    except Exception:
        return _perturbation_factors(model, row, raw_probability)


def _similar_cases(row: pd.DataFrame, limit: int = 5) -> list[SimilarHistoricalCase]:
    panel = _panel()
    if panel is None or panel.empty or TARGET not in panel.columns:
        return []
    # Evidence pool is limited to train + validation months, keeping the current held-out test month separate.
    _, metadata, _ = _load()
    evidence_end = str((metadata or {}).get("validation_split") or "2026-01")[:7]
    pool = panel[panel["snapshot_month"] <= evidence_end].copy()
    numeric = ["original_cost_crore", "expenditure_crore", "days_to_original_deadline", "expenditure_to_original_cost_pct"]
    usable = pool.dropna(subset=numeric + [TARGET, "project_code", "snapshot_month", "sector_name"]).copy()
    if usable.empty:
        return []

    target_sector = str(row.iloc[0]["sector_name"])
    means, stds = usable[numeric].mean(), usable[numeric].std().replace(0, 1).fillna(1)
    target_vec = (row.iloc[0][numeric].astype(float) - means) / stds
    matrix = (usable[numeric].astype(float) - means) / stds
    usable["_distance"] = np.sqrt(((matrix - target_vec) ** 2).sum(axis=1))
    usable["_same_sector"] = usable["sector_name"].astype(str).eq(target_sector)

    # Prefer same-sector precedents. Cross-sector examples are only used as a clearly-labelled fallback.
    same = (
        usable[usable["_same_sector"]]
        .sort_values("_distance")
        .drop_duplicates("project_code")
        .head(limit)
    )
    need = max(0, limit - len(same))
    if need:
        used_codes = set(same["project_code"].astype(str))
        fallback = (
            usable[~usable["_same_sector"] & ~usable["project_code"].astype(str).isin(used_codes)]
            .assign(_distance=lambda d: d["_distance"] + 1.25)
            .sort_values("_distance")
            .drop_duplicates("project_code")
            .head(need)
        )
        selected = pd.concat([same, fallback], ignore_index=True)
    else:
        selected = same.reset_index(drop=True)

    if selected.empty:
        return []
    max_distance = max(float(selected["_distance"].max()), 0.001)
    results = []
    for _, r in selected.iterrows():
        similarity = max(0, min(99, round(100 * (1 - float(r["_distance"]) / (max_distance + 2.5)))))
        results.append(SimilarHistoricalCase(
            project_code=str(r["project_code"]), snapshot_month=str(r["snapshot_month"]), sector_name=str(r["sector_name"]),
            similarity_pct=similarity, same_sector=bool(r["_same_sector"]),
            original_cost_crore=float(r["original_cost_crore"]),
            expenditure_to_original_cost_pct=float(r["expenditure_to_original_cost_pct"]),
            days_to_original_deadline=int(r["days_to_original_deadline"]),
            slipped_within_3_months=bool(int(r[TARGET])),
        ))
    return results





def _severity(days: int) -> str:
    if days <= 30:
        return "MINOR"
    if days <= 90:
        return "SIGNIFICANT"
    if days <= 180:
        return "SEVERE"
    return "CRITICAL"


def _delay_outlook(row: pd.DataFrame, probability: float) -> DelayOutlook | None:
    _load()
    if _DURATION_MODEL is None or _DURATION_METADATA is None:
        return None
    expected = max(1, int(round(float(np.expm1(_DURATION_MODEL.predict(row)[0])))))
    error = max(0, int(_DURATION_METADATA.get("likely_range_error_days", 0)))
    low = max(1, expected - error)
    high = max(low, expected + error)
    exposure = max(0, int(round(probability * expected)))
    return DelayOutlook(
        expected_extension_days=expected, likely_range_low_days=low, likely_range_high_days=high,
        expected_delay_exposure_days=exposure, severity=_severity(expected),
        model_name=_DURATION_METADATA.get("model_name"),
        conditional_note=("Conditional impact estimate: predicted extension magnitude if a schedule slip occurs. "
                          "The range reflects validation residual uncertainty; it is not a guaranteed calendar delay."),
    )

def risk_snapshot(project: Project) -> dict | None:
    """Lightweight current-risk score used by dashboard/GIS surfaces.

    It intentionally skips SHAP, analogue retrieval and recommendations so portfolio
    views can score multiple projects without performing expensive explanations.
    """
    model, metadata, calibrator = _load()
    if model is None or metadata is None:
        return None
    try:
        row = _frame(project)
    except ValueError:
        return None
    _, probability = _probabilities(model, calibrator, row)
    threshold = float(metadata.get("probability_threshold", 0.5))
    outlook = _delay_outlook(row, probability)
    return {
        "delay_probability": round(probability, 4),
        "risk_category": _risk(probability, threshold),
        "slip_alert": probability >= threshold,
        "probability_threshold": threshold,
        "delay_outlook": outlook,
    }


def _operational_priority(project: Project) -> tuple[str, str]:
    if int(project.legal_disputes or 0) > 0:
        return "Legal resolution", "Escalate authorized legal review"
    if int(project.pending_approvals or 0) > 0:
        return "Approval clearance", "Clear pending approval chain"
    if float(project.compensation_completion_pct or 0) < 70:
        return "Compensation", "Review compensation processing"
    if float(project.possession_pct or 0) < 70:
        return "Possession", "Review possession readiness"
    if float(project.rehabilitation_completion_pct or 0) < 70:
        return "Rehabilitation", "Review rehabilitation completion"
    return "No dominant recorded bottleneck", "Continue routine monitoring"


def _friction_schema(project: Project, overrides: dict | None = None) -> FrictionResult:
    f = friction_for(project, overrides)
    return FrictionResult(
        score=f.score, label=f.label, dominant_blocker=f.dominant_blocker,
        components=f.components, methodology=f.methodology,
    )



def _acquisition_risk_schema(project: Project, overrides: dict | None = None) -> AcquisitionDelayRisk:
    risk = acquisition_delay_risk_for(project, overrides)
    return AcquisitionDelayRisk(
        score=risk.score, label=risk.label, current_stage=risk.current_stage,
        stage_attention=risk.stage_attention, drivers=risk.drivers, methodology=risk.methodology,
    )


def portfolio_risk_pulse(projects: list[Project]) -> RiskPulseResponse:
    """Summarise model-scored projects for the signed-in operational scope."""
    _, metadata, _ = _load()
    if metadata is None:
        return RiskPulseResponse(
            model_available=False, scored_projects=0, unscored_projects=len(projects),
            high_risk=0, medium_risk=0, low_risk=0, intervention_candidates=0, projects=[]
        )
    threshold = float(metadata.get("probability_threshold", 0.5))
    scored: list[RiskPulseProject] = []
    unscored = 0
    for project in projects:
        snapshot = risk_snapshot(project)
        if snapshot is None:
            unscored += 1
            continue
        issues = int(project.pending_approvals > 0) + int(project.legal_disputes > 0) + int(project.compensation_completion_pct < 100) + int(project.possession_pct < 100)
        readiness = readiness_for(project)
        friction = friction_for(project)
        acquisition_risk = acquisition_delay_risk_for(project)
        priority_score, priority_category = intervention_priority(
            snapshot["delay_probability"], friction.score, readiness.readiness_score, acquisition_risk.score
        )
        scored.append(RiskPulseProject(
            project_id=project.project_id, project_name=project.project_name, state=project.state, district=project.district,
            delay_probability=snapshot["delay_probability"], risk_category=snapshot["risk_category"],
            slip_alert=snapshot["slip_alert"], operational_issue_count=issues,
            expected_extension_days=snapshot["delay_outlook"].expected_extension_days if snapshot.get("delay_outlook") else None,
            expected_delay_exposure_days=snapshot["delay_outlook"].expected_delay_exposure_days if snapshot.get("delay_outlook") else None,
            impact_severity=snapshot["delay_outlook"].severity if snapshot.get("delay_outlook") else None,
            primary_bottleneck=readiness.primary_blocker, suggested_action=_operational_priority(project)[1],
            acquisition_readiness_score=readiness.readiness_score, acquisition_readiness_label=readiness.readiness_label,
            acquisition_friction_score=friction.score, acquisition_friction_label=friction.label,
            acquisition_delay_risk_score=acquisition_risk.score, acquisition_delay_risk_label=acquisition_risk.label,
            intervention_priority_score=priority_score, intervention_priority_category=priority_category,
        ))
    scored.sort(key=lambda item: (item.intervention_priority_score or 0, item.acquisition_friction_score or 0, item.delay_probability), reverse=True)
    high = sum(item.risk_category == "HIGH" for item in scored)
    medium = sum(item.risk_category == "MEDIUM" for item in scored)
    low = sum(item.risk_category == "LOW" for item in scored)
    critical_priority = sum(item.intervention_priority_category == "CRITICAL" for item in scored)
    high_priority = sum(item.intervention_priority_category == "HIGH" for item in scored)
    average_friction = round(sum(item.acquisition_friction_score or 0 for item in scored) / len(scored)) if scored else 0
    average_acquisition_risk = round(sum(item.acquisition_delay_risk_score or 0 for item in scored) / len(scored)) if scored else 0
    return RiskPulseResponse(
        model_available=True, probability_threshold=threshold, scored_projects=len(scored), unscored_projects=unscored,
        high_risk=high, medium_risk=medium, low_risk=low,
        intervention_candidates=critical_priority + high_priority, critical_priority=critical_priority, high_priority=high_priority,
        average_friction_score=average_friction, average_acquisition_delay_risk_score=average_acquisition_risk,
        total_expected_delay_exposure_days=sum(item.expected_delay_exposure_days or 0 for item in scored), projects=scored,
    )

def predict(project: Project) -> PredictionResult:
    model, metadata, calibrator = _load()
    if model is None or metadata is None:
        raise RuntimeError("No trained model artifact is loaded")
    row = _frame(project)
    raw_probability, probability = _probabilities(model, calibrator, row)
    threshold = float(metadata.get("probability_threshold", 0.5))
    factors, explanation_method = _local_factors(model, row, raw_probability)
    readiness = readiness_for(project)
    friction = friction_for(project)
    acquisition_risk = acquisition_delay_risk_for(project)
    priority_score, priority_category = intervention_priority(probability, friction.score, readiness.readiness_score, acquisition_risk.score)
    return PredictionResult(
        project_id=project.project_id,
        delay_probability=round(probability, 4), raw_probability=round(raw_probability, 4),
        risk_score=round(probability * 100), risk_category=_risk(probability, threshold),
        predicted_delay_indicator=probability >= threshold, delay_outlook=_delay_outlook(row, probability),
        acquisition_friction=_friction_schema(project), acquisition_delay_risk=_acquisition_risk_schema(project), acquisition_readiness_score=readiness.readiness_score,
        intervention_priority_score=priority_score, intervention_priority_category=priority_category,
        factors=factors, similar_cases=_similar_cases(row), recommendations=recommendations_for(factors, project=project),
        metadata=ModelMetadata(
            available=True, model_name=metadata.get("model_name"), training_data_kind=metadata.get("training_data_kind"),
            explanation_method=explanation_method,
            calibration_method=metadata.get("calibration_method") if calibrator is not None else None,
            probability_kind="CALIBRATED" if calibrator is not None else "RAW_MODEL_PROBABILITY",
            probability_threshold=threshold,
            data_period=metadata.get("data_period"), target_definition=metadata.get("target_definition"),
            test_split=metadata.get("test_split"),
            model_role="PAIMANA central-infrastructure schedule-slip baseline",
            land_acquisition_features_used=False,
            operational_lane_note=("Compensation, possession, R&R, approvals, legal disputes and stakeholder response are used "
                                   "by LandGuard's separate operational friction/readiness lane; they are not inputs to this ML model."),
            validation_caveat=("Prototype temporal baseline. Treat the probability as an early-warning signal, not a validated "
                               "land-acquisition-delay probability or causal estimate."),
            disclaimer=metadata.get("disclaimer", "Prototype model."),
        ),
    )


def scenario(
    project: Project,
    expenditure_ratio: float,
    days_to_deadline: int | None = None,
    *,
    clear_pending_approvals: bool = False,
    resolve_legal_disputes: bool = False,
    compensation_target_pct: float | None = None,
    possession_target_pct: float | None = None,
    rehabilitation_target_pct: float | None = None,
    stakeholder_response_target_days: int | None = None,
) -> ScenarioResult:
    model, metadata, calibrator = _load()
    if model is None or metadata is None:
        raise RuntimeError("No trained model artifact is loaded")
    row = _frame(project)
    _, base = _probabilities(model, calibrator, row)
    scenario_row = row.copy()
    scenario_row.loc[0, "expenditure_to_original_cost_pct"] = float(expenditure_ratio)
    scenario_row.loc[0, "expenditure_crore"] = float(row.loc[0, "original_cost_crore"]) * float(expenditure_ratio) / 100.0
    effective_days = int(row.loc[0, "days_to_original_deadline"] if days_to_deadline is None else days_to_deadline)
    scenario_row.loc[0, "days_to_original_deadline"] = effective_days
    scenario_row.loc[0, "original_deadline_passed"] = int(effective_days < 0)
    _, changed = _probabilities(model, calibrator, scenario_row)
    base_outlook = _delay_outlook(row, base)
    scenario_outlook = _delay_outlook(scenario_row, changed)
    threshold = float(metadata.get("probability_threshold", 0.5))

    overrides = {}
    if clear_pending_approvals:
        overrides["pending_approvals"] = 0
    if resolve_legal_disputes:
        overrides["legal_disputes"] = 0
    if compensation_target_pct is not None:
        overrides["compensation_completion_pct"] = compensation_target_pct
    if possession_target_pct is not None:
        overrides["possession_pct"] = possession_target_pct
    if rehabilitation_target_pct is not None:
        overrides["rehabilitation_completion_pct"] = rehabilitation_target_pct
    if stakeholder_response_target_days is not None:
        overrides["stakeholder_response_days"] = stakeholder_response_target_days

    base_readiness = readiness_for(project)
    scenario_readiness = readiness_for(project, overrides=overrides)
    base_friction = friction_for(project)
    scenario_friction = friction_for(project, overrides)
    base_acquisition_risk = acquisition_delay_risk_for(project)
    scenario_acquisition_risk = acquisition_delay_risk_for(project, overrides)
    base_priority_score, base_priority_category = intervention_priority(base, base_friction.score, base_readiness.readiness_score, base_acquisition_risk.score)
    scenario_priority_score, scenario_priority_category = intervention_priority(changed, scenario_friction.score, scenario_readiness.readiness_score, scenario_acquisition_risk.score)

    return ScenarioResult(
        base_probability=round(base, 4), scenario_probability=round(changed, 4), probability_change=round(changed - base, 4),
        base_risk_category=_risk(base, threshold), scenario_risk_category=_risk(changed, threshold),
        base_alert=base >= threshold, scenario_alert=changed >= threshold,
        scenario_expenditure_to_original_cost_pct=round(float(expenditure_ratio), 1),
        scenario_days_to_original_deadline=effective_days,
        base_delay_outlook=base_outlook, scenario_delay_outlook=scenario_outlook,
        base_friction=_friction_schema(project), scenario_friction=_friction_schema(project, overrides),
        base_acquisition_delay_risk=_acquisition_risk_schema(project), scenario_acquisition_delay_risk=_acquisition_risk_schema(project, overrides),
        base_readiness_score=base_readiness.readiness_score, scenario_readiness_score=scenario_readiness.readiness_score,
        base_priority_score=base_priority_score, scenario_priority_score=scenario_priority_score,
        base_priority_category=base_priority_category, scenario_priority_category=scenario_priority_category,
        note=("Model-state sensitivity only: expenditure progress and time-to-deadline affect the PAIMANA baseline. "
              "They do not prove causal delay reduction."),
        operational_note=("Administrative selections change only the transparent Land-Acquisition Friction/Readiness lane. "
                          "They do not alter the ML probability unless model-state inputs are changed separately."),
    )
