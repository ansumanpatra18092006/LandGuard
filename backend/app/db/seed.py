from datetime import date

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.project import Project
from app.schemas.project import ProjectWrite

# Canonical SIH demo dataset. Every row is fictional/illustrative, but each row is
# model-ready so the full prediction workflow works immediately after seeding.
SEEDS = [
    dict(project_id="P-RGD-001", project_name="Rayagada Rural Road Expansion", project_type="ROAD",
         state="Odisha", district="Rayagada", latitude=19.1712, longitude=83.4163, land_area=188,
         affected_families=342, compensation_completion_pct=42, pending_approvals=3, legal_disputes=1,
         possession_pct=28, rehabilitation_completion_pct=22, stakeholder_response_days=36,
         elapsed_acquisition_days=310, acquisition_stage="COMPENSATION", original_cost_crore=650,
         expenditure_crore=210, original_end_date=date(2027,3,31)),
    dict(project_id="P-RGD-002", project_name="Rayagada Water Supply Corridor", project_type="URBAN",
         state="Odisha", district="Rayagada", latitude=19.1865, longitude=83.4018, land_area=96,
         affected_families=174, compensation_completion_pct=71, pending_approvals=1, legal_disputes=0,
         possession_pct=63, rehabilitation_completion_pct=68, stakeholder_response_days=14,
         elapsed_acquisition_days=245, acquisition_stage="REHABILITATION", original_cost_crore=420,
         expenditure_crore=278, original_end_date=date(2027,9,30)),
    dict(project_id="P-RGD-003", project_name="Rayagada Transmission Corridor", project_type="INDUSTRIAL",
         state="Odisha", district="Rayagada", latitude=19.2044, longitude=83.4491, land_area=132,
         affected_families=210, compensation_completion_pct=84, pending_approvals=0, legal_disputes=0,
         possession_pct=78, rehabilitation_completion_pct=81, stakeholder_response_days=8,
         elapsed_acquisition_days=190, acquisition_stage="POSSESSION", original_cost_crore=780,
         expenditure_crore=625, original_end_date=date(2028,2,29)),
    dict(project_id="P-RGD-004", project_name="Rayagada Industrial Access Road", project_type="ROAD",
         state="Odisha", district="Rayagada", latitude=19.1355, longitude=83.3912, land_area=221,
         affected_families=405, compensation_completion_pct=31, pending_approvals=4, legal_disputes=2,
         possession_pct=18, rehabilitation_completion_pct=26, stakeholder_response_days=52,
         elapsed_acquisition_days=420, acquisition_stage="COMPENSATION", original_cost_crore=980,
         expenditure_crore=175, original_end_date=date(2026,11,30)),
    dict(project_id="P-RGD-005", project_name="Rayagada Irrigation Link Project", project_type="IRRIGATION",
         state="Odisha", district="Rayagada", latitude=19.2282, longitude=83.4720, land_area=306,
         affected_families=512, compensation_completion_pct=56, pending_approvals=2, legal_disputes=0,
         possession_pct=44, rehabilitation_completion_pct=49, stakeholder_response_days=21,
         elapsed_acquisition_days=365, acquisition_stage="REHABILITATION", original_cost_crore=1120,
         expenditure_crore=476, original_end_date=date(2027,5,31)),
    dict(project_id="P-RGD-006", project_name="Rayagada District Connectivity Upgrade", project_type="ROAD",
         state="Odisha", district="Rayagada", latitude=19.1124, longitude=83.4385, land_area=264,
         affected_families=448, compensation_completion_pct=24, pending_approvals=5, legal_disputes=2,
         possession_pct=12, rehabilitation_completion_pct=19, stakeholder_response_days=61,
         elapsed_acquisition_days=510, acquisition_stage="COMPENSATION", original_cost_crore=860,
         expenditure_crore=118, original_end_date=date(2026,10,31)),
    dict(project_id="P-RGD-007", project_name="Rayagada Railway Approach Corridor", project_type="RAILWAY",
         state="Odisha", district="Rayagada", latitude=19.1578, longitude=83.4792, land_area=176,
         affected_families=286, compensation_completion_pct=66, pending_approvals=1, legal_disputes=1,
         possession_pct=51, rehabilitation_completion_pct=61, stakeholder_response_days=19,
         elapsed_acquisition_days=330, acquisition_stage="REHABILITATION", original_cost_crore=740,
         expenditure_crore=592, original_end_date=date(2027,3,18)),
    dict(project_id="P-RGD-008", project_name="Rayagada Public Utility Expansion", project_type="URBAN",
         state="Odisha", district="Rayagada", latitude=19.1951, longitude=83.3659, land_area=84,
         affected_families=136, compensation_completion_pct=93, pending_approvals=0, legal_disputes=0,
         possession_pct=91, rehabilitation_completion_pct=90, stakeholder_response_days=5,
         elapsed_acquisition_days=165, acquisition_stage="POSSESSION", original_cost_crore=360,
         expenditure_crore=318, original_end_date=date(2028,6,30)),
]


def main():
    created = 0
    updated = 0
    with SessionLocal() as db:
        for row in SEEDS:
            existing = db.scalar(select(Project).where(Project.project_id == row["project_id"]))
            payload = ProjectWrite(**row)
            if existing is None:
                db.add(Project(**payload.model_dump(), data_source="ILLUSTRATIVE"))
                created += 1
            elif existing.data_source == "ILLUSTRATIVE":
                for field, value in payload.model_dump().items():
                    setattr(existing, field, value)
                updated += 1
        db.commit()
    print(f"Canonical SIH demo dataset ready: {created} created, {updated} refreshed. All records are fictional illustrative data.")


if __name__ == "__main__":
    main()
