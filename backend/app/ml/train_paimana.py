"""Train the LandGuard real-data PAIMANA schedule-slip baseline.

The target is a forward-looking event derived from monthly PAIMANA snapshots:
"Will this project's reported completion schedule move later within the next
three months?"

Only features available at the snapshot date are used. Revised completion date,
delay days and revised cost are deliberately excluded from model inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, GradientBoostingRegressor, RandomForestRegressor, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    r2_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.paimana_features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, TARGET

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional candidate
    XGBClassifier = None

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = ROOT / "data" / "paimana_longitudinal_training.csv"
ARTIFACT_DIR = ROOT / "model_artifacts"


def _metrics(y, prob, threshold: float) -> dict:
    pred = (prob >= threshold).astype(int)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, prob)),
        "confusion_matrix": confusion_matrix(y, pred).tolist(),
    }


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        (
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]),
            NUMERIC_FEATURES,
        ),
        (
            "cat",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]),
            CATEGORICAL_FEATURES,
        ),
    ])



def _duration_targets(panel: pd.DataFrame) -> pd.DataFrame:
    """Derive future schedule-extension days from the raw monthly PAIMANA snapshots.

    For each project-month, the current effective schedule is revised_date when present,
    otherwise original_end_date. The target is the maximum *later* effective schedule
    observed within the next three reporting months, minus the current effective schedule.
    Only positive-extension rows are used to train the conditional duration regressor.
    """
    raw_dir = ROOT.parent / "data" / "raw" / "paimana" / "monthly"
    frames = []
    for csv_path in sorted(raw_dir.glob("paimana_dashboard_*.csv")):
        month = csv_path.stem.rsplit("_", 1)[-1]
        d = pd.read_csv(csv_path, dtype={"project_code": str})
        d["snapshot_month"] = month
        for col in ("original_end_date", "revised_date"):
            d[col] = pd.to_datetime(d[col], errors="coerce")
        d["effective_schedule_date"] = d["revised_date"].fillna(d["original_end_date"])
        frames.append(d[["project_code", "snapshot_month", "effective_schedule_date"]])
    if not frames:
        raise ValueError("Monthly PAIMANA CSVs are required under data/raw/paimana/monthly to train delay duration.")

    hist = pd.concat(frames, ignore_index=True).drop_duplicates(["project_code", "snapshot_month"], keep="last")
    hist = hist.sort_values(["project_code", "snapshot_month"]).reset_index(drop=True)
    targets = []
    by_project = {code: g.reset_index(drop=True) for code, g in hist.groupby("project_code", sort=False)}
    for _, row in hist.iterrows():
        current = row["effective_schedule_date"]
        if pd.isna(current):
            targets.append(np.nan); continue
        start = pd.Period(row["snapshot_month"], freq="M")
        g = by_project[row["project_code"]]
        offsets = g["snapshot_month"].map(lambda x: (pd.Period(x, freq="M") - start).n)
        future = g[(offsets >= 1) & (offsets <= 3)]["effective_schedule_date"].dropna()
        if future.empty:
            targets.append(np.nan); continue
        targets.append(max(0, int((future.max() - current).days)))
    hist["extension_days_next_3_months"] = targets
    return panel.merge(hist[["project_code", "snapshot_month", "extension_days_next_3_months"]], on=["project_code", "snapshot_month"], how="left")


def _regression_metrics(y, pred) -> dict:
    return {
        "mae_days": float(mean_absolute_error(y, pred)),
        "median_ae_days": float(median_absolute_error(y, pred)),
        "rmse_days": float(mean_squared_error(y, pred) ** 0.5),
        "r2": float(r2_score(y, pred)),
    }


def _train_duration_model(df: pd.DataFrame, artifact_dir: Path, train_end: str, val_month: str, test_month: str) -> dict:
    df = df.copy()
    df["project_code"] = df["project_code"].astype(str)
    duration_df = _duration_targets(df)
    train_df = duration_df[(duration_df.snapshot_month <= train_end) & (duration_df.extension_days_next_3_months > 0)].copy()
    val_df = duration_df[(duration_df.snapshot_month == val_month) & (duration_df.extension_days_next_3_months > 0)].copy()
    test_df = duration_df[(duration_df.snapshot_month == test_month) & (duration_df.extension_days_next_3_months > 0)].copy()
    if min(len(train_df), len(val_df), len(test_df)) == 0:
        raise ValueError("Not enough positive future schedule-extension events to train the duration model.")

    candidates = {
        "Random Forest Regressor": RandomForestRegressor(n_estimators=400, min_samples_leaf=4, random_state=26017, n_jobs=-1),
        "Gradient Boosting Regressor": GradientBoostingRegressor(n_estimators=250, learning_rate=0.04, max_depth=3, loss="huber", random_state=26017),
        "Extra Trees Regressor": ExtraTreesRegressor(n_estimators=400, min_samples_leaf=4, random_state=26017, n_jobs=-1),
    }
    fitted, comparison = {}, {}
    y_train = np.log1p(train_df["extension_days_next_3_months"].astype(float))
    for name, estimator in candidates.items():
        pipe = Pipeline([("preprocessor", _preprocessor()), ("model", estimator)])
        pipe.fit(train_df[FEATURES], y_train)
        comparison[name] = {}
        for split_name, split in (("validation", val_df), ("test", test_df)):
            pred = np.maximum(1.0, np.expm1(pipe.predict(split[FEATURES])))
            comparison[name][split_name] = _regression_metrics(split["extension_days_next_3_months"].astype(float), pred)
        fitted[name] = pipe

    best_name = min(comparison, key=lambda n: comparison[n]["validation"]["mae_days"])
    model = fitted[best_name]
    val_pred = np.maximum(1.0, np.expm1(model.predict(val_df[FEATURES])))
    val_abs = np.abs(val_df["extension_days_next_3_months"].astype(float).to_numpy() - val_pred)
    uncertainty = int(round(float(np.quantile(val_abs, 0.80))))
    test_pred = np.maximum(1.0, np.expm1(model.predict(test_df[FEATURES])))
    test_metrics = _regression_metrics(test_df["extension_days_next_3_months"].astype(float), test_pred)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_dir / "delay_duration_regressor.joblib")
    duration_meta = {
        "model_name": best_name,
        "target_definition": "Conditional schedule-extension magnitude in days when a later schedule date appears within the next 3 months",
        "features": FEATURES,
        "selection_metric": "validation_mae_days",
        "train_positive_events": int(len(train_df)),
        "validation_positive_events": int(len(val_df)),
        "test_positive_events": int(len(test_df)),
        "likely_range_error_days": uncertainty,
        "metrics": test_metrics,
        "all_model_metrics": comparison,
        "disclaimer": "Conditional impact model trained only on observed positive schedule-extension events. It estimates extension magnitude if slippage occurs; it does not guarantee an exact delay duration.",
    }
    (artifact_dir / "duration_metadata.json").write_text(json.dumps(duration_meta, indent=2), encoding="utf-8")
    return duration_meta

def train(panel_path: Path = DEFAULT_PANEL, artifact_dir: Path = ARTIFACT_DIR) -> dict:
    df = pd.read_csv(panel_path)
    missing = [c for c in ["snapshot_month", *FEATURES, TARGET] if c not in df.columns]
    if missing:
        raise ValueError("Training panel is missing: " + ", ".join(missing))

    labelled_months = sorted(str(m) for m in df["snapshot_month"].dropna().unique())
    if len(labelled_months) < 3:
        raise ValueError("At least three fully-labelled snapshot months are required for temporal train/validation/test splits.")
    test_month = labelled_months[-1]
    val_month = labelled_months[-2]
    train_end = labelled_months[-3]
    train_start = labelled_months[0]

    train_df = df[df.snapshot_month <= train_end].copy()
    val_df = df[df.snapshot_month == val_month].copy()
    test_df = df[df.snapshot_month == test_month].copy()
    if min(len(train_df), len(val_df), len(test_df)) == 0:
        raise ValueError("Dynamic temporal train/validation/test split produced an empty partition.")

    y_train = train_df[TARGET].astype(int)
    y_val = val_df[TARGET].astype(int)
    y_test = test_df[TARGET].astype(int)
    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)

    candidates = {
        "Logistic Regression": LogisticRegression(max_iter=2000, class_weight="balanced", random_state=26017),
        "Random Forest": RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=26017,
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=180,
            learning_rate=0.05,
            max_depth=3,
            random_state=26017,
        ),
    }
    if XGBClassifier is not None:
        candidates["XGBoost"] = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.9,
            scale_pos_weight=(negatives / positives) if positives else 1.0,
            eval_metric="logloss",
            random_state=26017,
            n_jobs=4,
        )

    fitted = {}
    comparison = {}
    for name, estimator in candidates.items():
        pipe = Pipeline([("preprocessor", _preprocessor()), ("model", estimator)])
        pipe.fit(train_df[FEATURES], y_train)
        val_prob = pipe.predict_proba(val_df[FEATURES])[:, 1]
        test_prob = pipe.predict_proba(test_df[FEATURES])[:, 1]
        comparison[name] = {
            "validation": _metrics(y_val, val_prob, 0.5),
            "test_at_0_5": _metrics(y_test, test_prob, 0.5),
        }
        fitted[name] = pipe

    # Select on validation F1 only. The held-out Feb test is not used for model selection.
    best_name = max(comparison, key=lambda n: comparison[n]["validation"]["f1"])
    model = fitted[best_name]

    # Tune a single operating threshold on validation F1, then lock it before test scoring.
    val_prob = model.predict_proba(val_df[FEATURES])[:, 1]
    thresholds = np.arange(0.30, 0.71, 0.01)
    threshold_scores = [(float(t), f1_score(y_val, (val_prob >= t).astype(int), zero_division=0)) for t in thresholds]
    threshold, _ = max(threshold_scores, key=lambda item: item[1])
    test_prob = model.predict_proba(test_df[FEATURES])[:, 1]

    # Platt-style probability calibration is fitted only on the validation month.
    # It improves probability reliability without touching the held-out test month.
    calibrator = LogisticRegression(random_state=26017)
    calibrator.fit(val_prob.reshape(-1, 1), y_val)
    calibrated_val_prob = calibrator.predict_proba(val_prob.reshape(-1, 1))[:, 1]
    calibrated_test_prob = calibrator.predict_proba(test_prob.reshape(-1, 1))[:, 1]

    # Re-tune the operating threshold on calibrated validation probabilities only.
    threshold_scores = [
        (float(t), f1_score(y_val, (calibrated_val_prob >= t).astype(int), zero_division=0))
        for t in np.arange(0.20, 0.81, 0.01)
    ]
    threshold, _ = max(threshold_scores, key=lambda item: item[1])
    held_out = _metrics(y_test, calibrated_test_prob, threshold)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    duration_metadata = _train_duration_model(df, artifact_dir, train_end, val_month, test_month)
    joblib.dump(model, artifact_dir / "classifier.joblib")
    joblib.dump(calibrator, artifact_dir / "probability_calibrator.joblib")

    metadata = {
        "model_name": best_name,
        "training_data_kind": "OFFICIAL_PAIMANA_LONGITUDINAL_BASELINE",
        "source": "MoSPI PAIMANA public dashboard monthly snapshots",
        "data_period": f"{train_start} to {test_month} labelled; source history extends beyond the test horizon",
        "target_definition": "Schedule completion date moves later within the next 3 months",
        "features": FEATURES,
        "selection_metric": "validation_f1",
        "probability_threshold": round(float(threshold), 4),
        "calibration_method": f"Platt scaling on the {val_month} validation month",
        "probability_kind": "CALIBRATED",
        "train_split": f"{train_start} through {train_end}",
        "validation_split": val_month,
        "test_split": f"{test_month} (future labels observed through the following 3 monthly snapshots)",
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "metrics": {k: v for k, v in held_out.items() if k != "confusion_matrix"},
        "confusion_matrix": held_out["confusion_matrix"],
        "all_model_metrics": comparison,
        "delay_duration_model": duration_metadata,
        "sklearn_version": sklearn.__version__,
        "disclaimer": (
            "Real-data infrastructure schedule-slip baseline trained on official MoSPI PAIMANA monthly snapshots. "
            "It is not yet a land-acquisition-specific validated government deployment model; LandGuard's compensation, "
            "possession, approval and dispute indicators remain separate operational decision-support inputs."
        ),
    }
    (artifact_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (artifact_dir / "model_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    args = parser.parse_args()
    print(json.dumps(train(args.panel), indent=2))


if __name__ == "__main__":
    main()
