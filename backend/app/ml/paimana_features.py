"""Feature contract for the real-data PAIMANA schedule-slip baseline."""

CATEGORICAL_FEATURES = ["sector_name"]
NUMERIC_FEATURES = [
    "original_cost_crore",
    "expenditure_crore",
    "days_to_original_deadline",
    "original_deadline_passed",
    "expenditure_to_original_cost_pct",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET = "will_schedule_slip_next_3_months"

PROJECT_TYPE_TO_SECTOR = {
    "ROAD": "Roads & Highways",
    "RAILWAY": "Railways",
    "IRRIGATION": "Water Resources",
    "INDUSTRIAL": "Real Estate",
    "URBAN": "Urban Public Transport",
}

DISPLAY_NAMES = {
    "sector_name": "Project sector",
    "original_cost_crore": "Original project cost",
    "expenditure_crore": "Cumulative expenditure",
    "days_to_original_deadline": "Time to original deadline",
    "original_deadline_passed": "Original deadline status",
    "expenditure_to_original_cost_pct": "Expenditure-to-cost ratio",
}
