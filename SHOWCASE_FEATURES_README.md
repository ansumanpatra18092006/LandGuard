# LandGuard SIH Showcase Patch

This cumulative patch adds the three presentation-focused features requested:

1. **District Risk Pulse** on the operational dashboard
2. **Predictive pulsing GIS markers** driven by the PAIMANA model score
3. **Full-screen Intervention Simulator** with current-vs-scenario risk

It also includes the earlier calibrated probability, historical analogues, same-sector preference,
two-variable scenario logic, and SHAP wording refinements so the patch is safe to apply over the
last uploaded `LandGuard_clean(2).zip`.

## Apply

Extract this ZIP directly into:

    C:\LandGuard

Allow Windows to replace matching files.

## Then retrain once

The cumulative patch includes the probability-calibration training code. Run:

    cd C:\LandGuard\backend
    python -m app.ml.train_paimana

This creates/refreshes:

    backend\model_artifacts\classifier.joblib
    backend\model_artifacts\probability_calibrator.joblib
    backend\model_artifacts\metadata.json

No new database migration is required.

## Restart

Backend:

    cd C:\LandGuard\backend
    uvicorn app.main:app --reload

Frontend:

    cd C:\LandGuard\frontend
    npm run dev

## What to demo

### Dashboard
Open `/dashboard`.

The **District Risk Pulse** shows:
- high / medium / low predictive counts
- how many projects cross the trained alert threshold
- the highest-risk project queue
- direct jump to the predictive GIS map

Projects missing model-baseline fields are counted as unscored, not silently guessed.

### GIS
Open `/map`.

Markers now use the model risk when available:
- green = low
- amber = medium
- red = high
- high-risk alert markers pulse
- marker labels show the model probability

Select a project to see its 3-month schedule-slip probability and launch the Intervention Simulator.

### Intervention Simulator
From the AI Intelligence tab or GIS inspector, choose **Launch full-screen simulator** / **Simulate intervention**.

The full-screen view compares:

    CURRENT STATE  ->  SCENARIO STATE

Model-sensitive controls:
- expenditure progress
- days to original deadline

Administrative actions are shown in a separate lane:
- approvals
- legal disputes
- compensation
- possession

Administrative checkboxes **do not alter the ML probability**. This is deliberate: PAIMANA did not
train the model on those land-acquisition variables.

The footer explicitly states:

    Scenario analysis shows model sensitivity, not causal impact.
    AI recommends; authorized officials decide.

## Verification

Backend suite on the patched code:

    87 passed, 1 skipped

The skip is the optional live PostgreSQL test.

The model artifact in the verification environment emitted a scikit-learn version warning because
it was trained under 1.9.1 while the verification container uses 1.8.0. Retraining locally with
`python -m app.ml.train_paimana` keeps your artifact aligned with your installed environment.
