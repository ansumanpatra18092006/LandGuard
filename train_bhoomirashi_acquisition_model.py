#!/usr/bin/env python3
"""
train_bhoomirashi_acquisition_model.py

Fast, leakage-aware acquisition-delay baseline for LandGuard.

Input:
    bhoomirashi_notification_pairs_clean.csv

Target:
    delay_over_365d

Validation:
    5-fold StratifiedGroupKFold by project_id where possible.
    Rows from the same project never appear in both train and validation.

Models:
    Logistic Regression
    Random Forest
    Gradient Boosting

Outputs:
    bhoomirashi_model_artifacts/
        acquisition_classifier.joblib
        metadata.json
        model_comparison.csv
        feature_columns.json

IMPORTANT:
This is a research baseline trained on chronology-matched Bhoomi Rashi
3A→3D project-context pairs. It is not a statutory-compliance model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


INPUT = Path("bhoomirashi_notification_pairs_clean.csv")
OUT = Path("bhoomirashi_model_artifacts")
OUT.mkdir(exist_ok=True)

TARGET = "delay_over_365d"
GROUP = "project_id"


def derive_project_type(name: str) -> str:
    s = str(name or "").lower()
    if any(k in s for k in ["rob", "bridge", "flyover"]):
        return "bridge_rob"
    if "bypass" in s:
        return "bypass"
    if any(k in s for k in ["four lane", "4 lane", "4-lane", "four-laning"]):
        return "four_laning"
    if any(k in s for k in ["two lane", "2 lane", "2-lane", "widening", "upgradation", "rehabilitation"]):
        return "road_upgrade"
    return "other"


def prepare(df: pd.DataFrame):
    df = df.copy()

    # Dates available at prediction time.
    df["three_A_date"] = pd.to_datetime(df["three_A_date"], errors="coerce")
    df["three_A_year"] = df["three_A_date"].dt.year
    df["three_A_month"] = df["three_A_date"].dt.month

    # Normalize numeric project fields if available.
    numeric_candidates = [
        "land_required_ha",
        "land_available_ha",
        "land_to_be_acquired_ha",
        "land_available_ratio",
    ]

    for c in numeric_candidates:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Derive land ratio if not already present.
    if (
        "land_available_ratio" not in df.columns
        and "land_required_ha" in df.columns
        and "land_available_ha" in df.columns
    ):
        den = pd.to_numeric(df["land_required_ha"], errors="coerce").replace(0, np.nan)
        df["land_available_ratio"] = pd.to_numeric(
            df["land_available_ha"], errors="coerce"
        ) / den

    # Derive project type from project name.
    name_col = None
    for candidate in ["project_name", "Project Name", "name"]:
        if candidate in df.columns:
            name_col = candidate
            break

    if name_col:
        df["derived_project_type"] = df[name_col].fillna("").map(derive_project_type)
    else:
        df["derived_project_type"] = "unknown"

    # RO/PD is a usable pre-outcome regional/implementing context if present.
    ro_col = None
    for candidate in ["ro_pd_name", "RO/PD Name", "ro_pd"]:
        if candidate in df.columns:
            ro_col = candidate
            break

    if ro_col:
        df["ro_pd_category"] = df[ro_col].fillna("UNKNOWN").astype(str)
    else:
        df["ro_pd_category"] = "UNKNOWN"

    # ------------------------------
    # History features known by 3A date
    # ------------------------------
    df = df.sort_values([GROUP, "three_A_date"]).copy()

    df["prior_3A_count"] = df.groupby(GROUP).cumcount()

    # Previous 3A interval.
    prev_a = df.groupby(GROUP)["three_A_date"].shift(1)
    df["days_since_previous_3A"] = (df["three_A_date"] - prev_a).dt.days

    # Do NOT use three_D_date, days_3A_to_3D, or outcome-derived fields.
    numeric_features = [
        c for c in [
            "land_required_ha",
            "land_available_ha",
            "land_to_be_acquired_ha",
            "land_available_ratio",
            "three_A_year",
            "three_A_month",
            "prior_3A_count",
            "days_since_previous_3A",
        ]
        if c in df.columns
    ]

    categorical_features = [
        "derived_project_type",
        "ro_pd_category",
    ]

    # Keep only rows with target/group.
    df = df[df[TARGET].notna() & df[GROUP].notna()].copy()
    df[TARGET] = df[TARGET].astype(int)

    X = df[numeric_features + categorical_features].copy()
    y = df[TARGET].copy()
    groups = df[GROUP].astype(str).copy()

    return df, X, y, groups, numeric_features, categorical_features


def build_preprocessor(num_cols, cat_cols):
    num_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    return ColumnTransformer([
        ("num", num_pipe, num_cols),
        ("cat", cat_pipe, cat_cols),
    ])


def metrics(y_true, pred, prob):
    return {
        "accuracy": accuracy_score(y_true, pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, prob) if len(np.unique(y_true)) == 2 else np.nan,
    }


def main():
    if not INPUT.exists():
        raise SystemExit(f"Missing {INPUT}")

    raw = pd.read_csv(INPUT, low_memory=False)
    df, X, y, groups, num_cols, cat_cols = prepare(raw)

    print("=" * 72)
    print("LANDGUARD — BHOOMI RASHI ACQUISITION ML")
    print("=" * 72)
    print("Rows:", len(df))
    print("Projects:", groups.nunique())
    print("Target:")
    print(y.value_counts().sort_index())
    print()
    print("Numeric features:", num_cols)
    print("Categorical features:", cat_cols)
    print()

    model_defs = {
        "Logistic Regression": LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=42,
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=400,
            max_depth=None,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            random_state=42,
        ),
    }

    cv = StratifiedGroupKFold(
        n_splits=5,
        shuffle=True,
        random_state=42,
    )

    summary_rows = []

    for model_name, estimator in model_defs.items():
        fold_metrics = []
        print(f"\n[{model_name}]")

        for fold, (tr, va) in enumerate(cv.split(X, y, groups), start=1):
            pre = build_preprocessor(num_cols, cat_cols)

            pipe = Pipeline([
                ("preprocess", pre),
                ("model", estimator),
            ])

            pipe.fit(X.iloc[tr], y.iloc[tr])
            pred = pipe.predict(X.iloc[va])
            prob = pipe.predict_proba(X.iloc[va])[:, 1]

            m = metrics(y.iloc[va], pred, prob)
            fold_metrics.append(m)

            print(
                f"  fold {fold}: "
                f"bal_acc={m['balanced_accuracy']:.3f} "
                f"precision={m['precision']:.3f} "
                f"recall={m['recall']:.3f} "
                f"f1={m['f1']:.3f} "
                f"auc={m['roc_auc']:.3f}"
            )

        avg = {
            key: float(np.nanmean([m[key] for m in fold_metrics]))
            for key in fold_metrics[0]
        }
        std = {
            key: float(np.nanstd([m[key] for m in fold_metrics]))
            for key in fold_metrics[0]
        }

        summary_rows.append({
            "model": model_name,
            **{f"mean_{k}": v for k, v in avg.items()},
            **{f"std_{k}": v for k, v in std.items()},
        })

    comparison = pd.DataFrame(summary_rows).sort_values(
        ["mean_f1", "mean_roc_auc", "mean_recall"],
        ascending=False,
    )

    print("\n" + "=" * 72)
    print("MODEL COMPARISON")
    print("=" * 72)
    cols = [
        "model",
        "mean_balanced_accuracy",
        "mean_precision",
        "mean_recall",
        "mean_f1",
        "mean_roc_auc",
    ]
    print(comparison[cols].to_string(index=False))

    best_name = comparison.iloc[0]["model"]
    print(f"\nSelected by mean CV F1: {best_name}")

    # Final fit on all cleaned research data.
    final_pre = build_preprocessor(num_cols, cat_cols)
    final_pipe = Pipeline([
        ("preprocess", final_pre),
        ("model", model_defs[best_name]),
    ])
    final_pipe.fit(X, y)

    joblib.dump(final_pipe, OUT / "acquisition_classifier.joblib")
    comparison.to_csv(OUT / "model_comparison.csv", index=False)

    with open(OUT / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump({
            "numeric_features": num_cols,
            "categorical_features": cat_cols,
        }, f, indent=2)

    metadata = {
        "source": "Public Bhoomi Rashi project/notification records",
        "dataset_rows": int(len(df)),
        "unique_projects": int(groups.nunique()),
        "target": "delay_over_365d",
        "target_definition": (
            "1 when chronology-matched project-context 3A→3D interval "
            "exceeds 365 days; 0 otherwise"
        ),
        "pairing_method": "deduped_nearest_subsequent_3D",
        "geography_verified": False,
        "statutory_compliance_model": False,
        "validation": "5-fold StratifiedGroupKFold grouped by project_id",
        "selected_model": str(best_name),
        "selection_metric": "mean cross-validated F1",
        "class_counts": {
            str(k): int(v) for k, v in y.value_counts().sort_index().items()
        },
        "features": num_cols + cat_cols,
        "excluded_leakage_fields": [
            "three_D_date",
            "three_D_notification",
            "days_3A_to_3D",
            "delay_over_365d_as_input",
        ],
        "cv_metrics": comparison.to_dict(orient="records"),
        "recommended_label": "Experimental Bhoomi Rashi acquisition-stage ML",
    }

    with open(OUT / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\nSaved:")
    print(" ", OUT / "acquisition_classifier.joblib")
    print(" ", OUT / "model_comparison.csv")
    print(" ", OUT / "feature_columns.json")
    print(" ", OUT / "metadata.json")
    print()
    print("Use wording:")
    print(
        '  "Experimental acquisition-stage delay model trained on '
        'chronology-matched public Bhoomi Rashi records, validated '
        'with project-grouped cross-validation."'
    )


if __name__ == "__main__":
    main()
