# LandGuard real-data delay baseline

This patch replaces the illustrative synthetic classifier with a longitudinal baseline trained from **official MoSPI PAIMANA public-dashboard monthly snapshots**.

## Prediction target

For a project observed in month **T**:

> Will the reported project completion schedule move to a later date within the next 3 months?

The target is generated from future monthly snapshots. The model never receives `revised_date`, `delay_days`, or `revised_cost` as input features.

## Data and time split

- Source months collected: **2025-07 through 2026-05**
- Training snapshots: **2025-07 through 2025-12** — 5,420 rows
- Validation snapshot: **2026-01** — 1,702 rows
- Held-out test snapshot: **2026-02** — 1,948 rows
- February targets are determined only from later snapshots through May 2026.

This is a time-based evaluation, not a random train/test split.

## Model comparison

Candidate models:

- Logistic Regression
- Random Forest
- Gradient Boosting
- XGBoost

Model selection used **validation F1 only**. Random Forest was selected.

Held-out February test metrics using the threshold fixed from January validation:

- Accuracy: **0.8244**
- Balanced accuracy: **0.8303**
- Precision: **0.7593**
- Recall: **0.9078**
- F1: **0.8269**
- ROC-AUC: **0.9214**
- Confusion matrix: `[[789, 259], [83, 817]]`

These are real held-out metrics for this PAIMANA schedule-slip baseline. They are **not** validation of a production land-acquisition model.

## Inputs used by the model

- project sector (derived from LandGuard project type)
- original approved project cost
- cumulative expenditure
- days to original completion deadline
- whether the original deadline has passed
- expenditure / original-cost ratio

LandGuard fields such as compensation progress, possession, legal disputes and pending approvals are deliberately **not claimed as model features** because PAIMANA did not provide them in this training dataset. They remain separate operational indicators and can drive clearly labelled administrative recommendations.

## After extracting the patch

### 1. Apply the migration

```powershell
cd C:\LandGuard\backend
alembic upgrade head
```

Migration head becomes:

```text
0004_paimana_prediction_fields
```

### 2. Rebuild the model once on your own machine

The included artifact was trained during patch generation. Because scikit-learn joblib artifacts are version-sensitive, regenerate it with your installed scikit-learn version:

```powershell
python -m app.ml.train_paimana
```

This uses:

```text
backend\data\paimana_longitudinal_training.csv
```

and rewrites:

```text
backend\model_artifacts\classifier.joblib
backend\model_artifacts\metadata.json
backend\model_artifacts\model_comparison.json
```

### 3. Give the illustrative Rayagada records prediction-baseline fields

Open Supabase SQL Editor and run:

```text
backend\supabase\003_demo_prediction_inputs.sql
```

Those values are explicitly fictional demo inputs; they are not claims about real Rayagada government projects.

### 4. Restart backend

```powershell
uvicorn app.main:app --reload
```

Then open a project > **AI Intelligence** > **Run intelligence**.

## What the result means

The returned percentage estimates the model's learned probability of a **3-month schedule-slip event**, based on patterns learned from PAIMANA project histories.

SHAP explains the model contribution from the schedule/cost baseline. Land-acquisition recommendations based on approvals, disputes and compensation are displayed separately and explicitly identified as operational indicators.

## SIH-safe claim

A defensible description is:

> “LandGuard's current predictive baseline is trained on longitudinal MoSPI PAIMANA project-monitoring snapshots using a time-based holdout. It predicts near-term schedule revision risk. Land-acquisition-specific operational indicators are integrated separately today, and can be incorporated directly into retraining as longitudinal LACRRIS/state acquisition data becomes available.”
