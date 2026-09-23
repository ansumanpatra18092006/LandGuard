# Bhoomi Rashi acquisition-ML integration

This build integrates the trained experimental Bhoomi Rashi acquisition-stage classifier into LandGuard as a **separate supporting ML signal**.

## Backend

New endpoint:

```text
GET /api/v1/projects/{project_id}/bhoomirashi-predict
```

The endpoint loads:

```text
backend/model_artifacts/bhoomirashi/acquisition_classifier.joblib
backend/model_artifacts/bhoomirashi/metadata.json
backend/model_artifacts/bhoomirashi/feature_columns.json
backend/model_artifacts/bhoomirashi/model_comparison.csv
```

The artifact was trained with scikit-learn 1.9.1, which matches `backend/requirements.txt`.

## Current project-feature mapping

The historical model expects Bhoomi Rashi notification/project features that are not all present in the current LandGuard registry. LandGuard therefore exposes the signal with an explicit coverage/caveat card rather than pretending all features are directly observed.

Direct field:

- `land_required_ha <- land_area`

Explicit proxy mappings:

- `land_available_ha <- land_area × possession_pct`
- `land_to_be_acquired_ha <- land_area − derived available land`
- `land_available_ratio <- possession_pct / 100`
- `derived_project_type <- project_name text category`

Missing historical fields are left missing and handled by the fitted training pipeline's imputers:

- `three_A_year`
- `three_A_month`
- `prior_3A_count`
- `days_since_previous_3A`
- `ro_pd_category`

No fake 3A history is invented.

## Frontend

Project → **AI Intelligence** now automatically shows an **Experimental Acquisition ML** card with:

- Bhoomi Rashi probability
- LOW / MODERATE / HIGH research label
- 1,365 cleaned observations / 432 projects
- grouped-CV ROC-AUC, F1 and recall
- current input coverage
- explicit proxy/imputation disclosure
- chronology-matching/statutory-compliance caveat

This signal is intentionally separate from:

- transparent Acquisition Delay Risk
- Readiness / Friction
- PAIMANA 3-month wider-project schedule signal

## Presentation wording

> Experimental acquisition-stage delay model trained on chronology-matched public Bhoomi Rashi records and validated with project-grouped cross-validation. It is supporting research evidence, not a statutory-compliance score.

Current grouped-CV metrics for the selected Logistic Regression baseline:

- ROC-AUC: 0.6303
- F1: 0.3709
- Recall: 0.5424

Do not call ROC-AUC "accuracy".
