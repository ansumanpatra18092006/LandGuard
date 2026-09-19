"""Train LandGuard AI candidate classifiers.

The included generator creates ILLUSTRATIVE SYNTHETIC data solely so the full
prototype pipeline can be demonstrated. Metrics produced from synthetic data
must never be presented as government/field validation results.

For real training:
    python -m app.ml.train --csv path/to/labeled_projects.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, TARGET

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "model_artifacts"
DATA_DIR = ROOT / "data"


def synthetic_dataset(rows: int = 600, seed: int = 26017) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    project_types = np.array(["ROAD", "RAILWAY", "IRRIGATION", "INDUSTRIAL", "URBAN"])
    stages = np.array(["NOTIFICATION", "SURVEY", "VALUATION", "COMPENSATION", "REHABILITATION", "POSSESSION", "COMPLETED"])
    df = pd.DataFrame({
        "project_type": rng.choice(project_types, rows),
        "acquisition_stage": rng.choice(stages, rows),
        "land_area": np.round(rng.gamma(2.3, 50, rows), 2),
        "affected_families": rng.integers(5, 700, rows),
        "compensation_completion_pct": np.round(rng.uniform(5, 100, rows), 1),
        "pending_approvals": rng.integers(0, 6, rows),
        "legal_disputes": rng.integers(0, 5, rows),
        "possession_pct": np.round(rng.uniform(0, 100, rows), 1),
        "rehabilitation_completion_pct": np.round(rng.uniform(0, 100, rows), 1),
        "stakeholder_response_days": rng.integers(1, 90, rows),
        "elapsed_acquisition_days": rng.integers(30, 1300, rows),
    })
    score = (
        0.45 * (df.legal_disputes > 0)
        + 0.38 * (df.pending_approvals >= 2)
        + 0.30 * (df.compensation_completion_pct < 55)
        + 0.24 * (df.possession_pct < 45)
        + 0.22 * (df.rehabilitation_completion_pct < 45)
        + 0.22 * (df.stakeholder_response_days > 35)
        + 0.24 * (df.elapsed_acquisition_days > 600)
        + rng.normal(0, 0.22, rows)
    )
    df[TARGET] = (score > 0.83).astype(int)
    return df


def validate_dataset(df: pd.DataFrame):
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if len(df) < 50:
        raise ValueError("At least 50 labelled records are required for prototype training.")
    if df[TARGET].nunique() < 2:
        raise ValueError("Target must contain both delayed and not-delayed classes.")


def train(df: pd.DataFrame, data_kind: str):
    validate_dataset(df)
    X, y = df[FEATURES], df[TARGET].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.25, stratify=y, random_state=26017)
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])
    candidates = {
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "Random Forest": RandomForestClassifier(n_estimators=220, random_state=26017, class_weight="balanced"),
        "Gradient Boosting": GradientBoostingClassifier(random_state=26017),
    }
    if XGBClassifier is not None:
        candidates["XGBoost"] = XGBClassifier(n_estimators=220, max_depth=4, learning_rate=.05, subsample=.9, colsample_bytree=.9, eval_metric="logloss", random_state=26017)
    results = []
    fitted = {}
    for name, model in candidates.items():
        pipe = Pipeline([("preprocessor", pre), ("model", model)])
        pipe.fit(X_train, y_train)
        pred = pipe.predict(X_test)
        prob = pipe.predict_proba(X_test)[:, 1]
        metrics = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "precision": float(precision_score(y_test, pred, zero_division=0)),
            "recall": float(recall_score(y_test, pred, zero_division=0)),
            "f1": float(f1_score(y_test, pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, prob)),
        }
        results.append((name, metrics))
        fitted[name] = pipe
    best_name, best_metrics = max(results, key=lambda item: item[1]["f1"])
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted[best_name], ARTIFACT_DIR / "classifier.joblib")
    metadata = {
        "model_name": best_name,
        "training_data_kind": data_kind,
        "metrics": best_metrics,
        "all_model_metrics": {name: values for name, values in results},
        "selection_metric": "f1",
        "disclaimer": "Prototype metrics only. Not validated on official government land-acquisition data." if data_kind != "OFFICIAL_VALIDATED" else "Model validation metadata supplied by implementation team.",
    }
    (ARTIFACT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv")
    parser.add_argument("--synthetic", action="store_true", help="Train an explicitly illustrative synthetic demo model")
    args = parser.parse_args()
    if args.csv:
        df = pd.read_csv(args.csv)
        metadata = train(df, "USER_SUPPLIED_LABELLED_DATA")
    elif args.synthetic:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df = synthetic_dataset()
        df.to_csv(DATA_DIR / "illustrative_synthetic_training.csv", index=False)
        metadata = train(df, "ILLUSTRATIVE_SYNTHETIC")
    else:
        raise SystemExit("Pass --csv <labelled.csv> or --synthetic. No model is trained implicitly.")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
