from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.models.project import Project
from app.schemas.intelligence import BhoomiRashiSignal

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "model_artifacts" / "bhoomirashi"
_MODEL = None
_METADATA = None


def _load():
    global _MODEL, _METADATA
    model_path = ARTIFACT_DIR / "acquisition_classifier.joblib"
    metadata_path = ARTIFACT_DIR / "metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        return None, None
    if _MODEL is None:
        _MODEL = joblib.load(model_path)
        _METADATA = json.loads(metadata_path.read_text(encoding="utf-8"))
    return _MODEL, _METADATA


def _project_type(name: str) -> str:
    value = (name or "").lower()
    if any(k in value for k in ("rob", "bridge", "flyover")):
        return "bridge_rob"
    if "bypass" in value:
        return "bypass"
    if any(k in value for k in ("four lane", "4 lane", "4-lane", "four-laning")):
        return "four_laning"
    if any(k in value for k in ("two lane", "2 lane", "2-lane", "widening", "upgradation", "rehabilitation")):
        return "road_upgrade"
    return "other"


def _frame(project: Project) -> tuple[pd.DataFrame, list[str], list[str], int]:
    """Build the model feature contract from fields LandGuard actually has.

    Public Bhoomi Rashi training features include several notification-history fields
    that are not present in the current LandGuard project registry. Those values are
    intentionally left missing so the fitted pipeline's training-set imputers handle
    them. We do not invent 3A dates/counts.

    Land-area mapping is explicit and marked as proxy-derived in the response:
      land_required_ha      <- LandGuard land_area
      land_available_ha     <- land_area * possession_pct
      land_to_be_acquired   <- remaining land area
      land_available_ratio  <- possession_pct / 100
    """
    land = float(project.land_area or 0.0)
    possession = max(0.0, min(100.0, float(project.possession_pct or 0.0)))
    available = land * possession / 100.0
    remaining = max(0.0, land - available)

    row = {
        "land_required_ha": land,
        "land_available_ha": available,
        "land_to_be_acquired_ha": remaining,
        "land_available_ratio": possession / 100.0 if land > 0 else np.nan,
        "three_A_year": np.nan,
        "three_A_month": np.nan,
        "prior_3A_count": np.nan,
        "days_since_previous_3A": np.nan,
        "derived_project_type": _project_type(project.project_name),
        "ro_pd_category": "UNKNOWN",
    }
    proxy_fields = [
        "land_available_ha <- land_area × possession_pct",
        "land_to_be_acquired_ha <- land_area − derived available land",
        "land_available_ratio <- possession_pct / 100",
        "derived_project_type <- project_name text category",
    ]
    imputed_fields = [
        "three_A_year",
        "three_A_month",
        "prior_3A_count",
        "days_since_previous_3A",
        "ro_pd_category",
    ]
    directly_available = 1  # land_required_ha
    proxy_available = 4
    coverage = round((directly_available + proxy_available) / 10 * 100)
    return pd.DataFrame([row]), proxy_fields, imputed_fields, coverage


def predict_bhoomirashi(project: Project) -> BhoomiRashiSignal:
    model, metadata = _load()
    if model is None or metadata is None:
        return BhoomiRashiSignal(
            available=False,
            project_id=project.project_id,
            label="UNAVAILABLE",
            disclaimer="Experimental Bhoomi Rashi model artifact is not loaded.",
        )

    row, proxy_fields, imputed_fields, coverage = _frame(project)
    probability = float(model.predict_proba(row)[0, 1])
    if probability < 0.35:
        label = "LOW"
    elif probability < 0.60:
        label = "MODERATE"
    else:
        label = "HIGH"

    comparison = (metadata.get("cv_metrics") or [{}])[0]
    return BhoomiRashiSignal(
        available=True,
        project_id=project.project_id,
        probability=round(probability, 4),
        label=label,
        model_name=metadata.get("selected_model", "Logistic Regression"),
        dataset_rows=int(metadata.get("dataset_rows", 0)),
        unique_projects=int(metadata.get("unique_projects", 0)),
        mean_roc_auc=round(float(comparison.get("mean_roc_auc", 0.0)), 4),
        mean_f1=round(float(comparison.get("mean_f1", 0.0)), 4),
        mean_recall=round(float(comparison.get("mean_recall", 0.0)), 4),
        input_coverage_pct=coverage,
        proxy_fields=proxy_fields,
        imputed_fields=imputed_fields,
        target_definition=metadata.get("target_definition"),
        validation=metadata.get("validation"),
        pairing_method=metadata.get("pairing_method"),
        geography_verified=bool(metadata.get("geography_verified", False)),
        disclaimer=(
            "Experimental supporting signal only. Training labels are chronology-matched public Bhoomi Rashi "
            "3A→3D research pairs, not geography-verified statutory matches. The current LandGuard project schema "
            "does not contain all notification-history inputs, so missing fields are handled by the trained pipeline's imputers."
        ),
    )
