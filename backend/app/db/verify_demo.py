"""Verify that the canonical illustrative SIH dataset exercises the full intelligence path."""
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.project import Project
from app.services.intelligence_service import risk_snapshot
from app.services.readiness_service import readiness_for


def main():
    with SessionLocal() as db:
        rows = db.scalars(select(Project).where(Project.project_id.like("P-RGD-%")).order_by(Project.project_id)).all()
        if len(rows) < 8:
            print("Demo verification failed: run `python -m app.db.seed` first.")
            return 2
        categories = set()
        print("Project       Risk   Readiness   Blocker")
        print("------------  -----  ----------  ------------------------")
        for project in rows:
            snapshot = risk_snapshot(project)
            if snapshot is None:
                print(f"{project.project_id:<12}  N/A    model input missing")
                return 2
            readiness = readiness_for(project)
            categories.add(snapshot["risk_category"])
            print(f"{project.project_id:<12}  {round(snapshot['delay_probability']*100):>3}% {snapshot['risk_category']:<6}  {readiness.readiness_score:>3}/100 {readiness.readiness_label:<11} {readiness.primary_blocker}")
        missing = {"LOW", "MEDIUM", "HIGH"} - categories
        if missing:
            print(f"Warning: current trained artifact does not produce all demo risk bands; missing {sorted(missing)}.")
            return 1
        print("Demo verification passed: LOW, MEDIUM and HIGH predictive cases are available.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
