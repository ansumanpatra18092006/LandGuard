"""Build the longitudinal PAIMANA training panel from monthly dashboard snapshots.

A row is labelled only when three complete future reporting months are available.
The target is 1 when the project's effective completion date moves later within
those next three monthly snapshots, otherwise 0.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.paimana_features import FEATURES, TARGET

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_RAW_DIR = PROJECT_DIR / "data" / "raw" / "paimana" / "monthly"
DEFAULT_OUTPUT = BACKEND_DIR / "data" / "paimana_longitudinal_training.csv"


def _month_from_path(path: Path) -> str:
    return path.stem.rsplit("_", 1)[-1]


def build_panel(raw_dir: Path = DEFAULT_RAW_DIR, output_path: Path = DEFAULT_OUTPUT) -> dict:
    paths = sorted(raw_dir.glob("paimana_dashboard_*.csv"))
    if len(paths) < 4:
        raise ValueError("At least four monthly PAIMANA snapshots are required to build forward 3-month labels.")

    frames: list[pd.DataFrame] = []
    for path in paths:
        month = _month_from_path(path)
        df = pd.read_csv(path, dtype={"project_code": str})
        required = {
            "project_code", "sector_name", "original_cost_crore", "expenditure_crore",
            "original_end_date", "revised_date",
        }
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")

        df["snapshot_month"] = month
        df["snapshot_date"] = pd.Period(month, freq="M").end_time.normalize()
        for col in ("original_end_date", "revised_date"):
            df[col] = pd.to_datetime(df[col], errors="coerce")
        for col in ("original_cost_crore", "expenditure_crore"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["effective_schedule_date"] = df["revised_date"].fillna(df["original_end_date"])
        df["days_to_original_deadline"] = (df["original_end_date"] - df["snapshot_date"]).dt.days
        df["original_deadline_passed"] = (
            df["original_end_date"].notna() & (df["original_end_date"] < df["snapshot_date"])
        ).astype(int)
        df["expenditure_to_original_cost_pct"] = np.where(
            df["original_cost_crore"].notna()
            & (df["original_cost_crore"] > 0)
            & df["expenditure_crore"].notna(),
            df["expenditure_crore"] / df["original_cost_crore"] * 100,
            np.nan,
        )
        frames.append(df)

    history = pd.concat(frames, ignore_index=True)
    history = history.drop_duplicates(["project_code", "snapshot_month"], keep="last")
    months = sorted(history["snapshot_month"].unique())
    month_set = set(months)

    by_project = {str(code): g.set_index("snapshot_month") for code, g in history.groupby("project_code", sort=False)}
    targets: list[float] = []
    complete_horizon: list[bool] = []

    for row in history.itertuples(index=False):
        start = pd.Period(row.snapshot_month, freq="M")
        future_months = [str(start + i) for i in (1, 2, 3)]
        complete = all(m in month_set for m in future_months)
        complete_horizon.append(complete)
        current = row.effective_schedule_date
        if not complete or pd.isna(current):
            targets.append(np.nan)
            continue
        project = by_project[str(row.project_code)]
        future_dates = []
        for m in future_months:
            if m in project.index:
                candidate = project.loc[m, "effective_schedule_date"]
                if isinstance(candidate, pd.Series):
                    candidate = candidate.iloc[-1]
                if pd.notna(candidate):
                    future_dates.append(candidate)
        if not future_dates:
            targets.append(np.nan)
        else:
            targets.append(int(max(future_dates) > current))

    history[TARGET] = pd.array(targets, dtype="Float64")
    history["complete_3_month_horizon"] = complete_horizon

    labelled = history[history[TARGET].notna()].copy()
    labelled[TARGET] = labelled[TARGET].astype(int)

    keep = [
        "project_code", "snapshot_month", "sector_name", "line_ministry",
        *[c for c in FEATURES if c not in {"sector_name"}], TARGET,
    ]
    keep = [c for c in keep if c in labelled.columns]
    panel = labelled[keep].sort_values(["snapshot_month", "project_code"]).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_path, index=False)

    latest_snapshot = months[-1]
    latest_labelled = str(panel["snapshot_month"].max()) if not panel.empty else None
    report = {
        "raw_snapshot_months": months,
        "latest_source_snapshot": latest_snapshot,
        "latest_fully_labelled_snapshot": latest_labelled,
        "panel_rows": int(len(panel)),
        "unique_projects": int(panel["project_code"].nunique()),
        "positive_rows": int(panel[TARGET].sum()),
        "negative_rows": int((panel[TARGET] == 0).sum()),
        "output": str(output_path),
    }
    (output_path.parent / "paimana_panel_quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_panel(), indent=2))
