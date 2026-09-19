NUMERIC_FEATURES = [
    "land_area",
    "affected_families",
    "compensation_completion_pct",
    "pending_approvals",
    "legal_disputes",
    "possession_pct",
    "rehabilitation_completion_pct",
    "stakeholder_response_days",
    "elapsed_acquisition_days",
]
CATEGORICAL_FEATURES = ["project_type", "acquisition_stage"]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET = "delayed"

DISPLAY_NAMES = {
    "land_area": "Land area",
    "affected_families": "Affected families",
    "compensation_completion_pct": "Compensation progress",
    "pending_approvals": "Pending approvals",
    "legal_disputes": "Legal disputes",
    "possession_pct": "Possession progress",
    "rehabilitation_completion_pct": "Rehabilitation progress",
    "stakeholder_response_days": "Stakeholder response time",
    "elapsed_acquisition_days": "Elapsed acquisition duration",
    "project_type": "Project type",
    "acquisition_stage": "Acquisition stage",
}
