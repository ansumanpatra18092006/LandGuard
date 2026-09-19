# LandGuard PAIMANA Continuous-Learning Pipeline

This patch turns the existing PAIMANA ingestion/training workflow into a monitored pipeline.

## What it does

1. Checks the official public PAIMANA dashboard on a schedule.
2. Reads the latest published/frozen reporting month.
3. Detects months not yet present under `data/raw/paimana/monthly`.
4. Downloads each missing monthly Project Overview snapshot through the same public dashboard POST flow used by the manual extractor.
5. Validates and stores the monthly CSV exactly once.
6. Rebuilds `backend/data/paimana_longitudinal_training.csv`.
7. Labels a project-month only when three complete future reporting months exist.
8. Retrains a challenger only when a newer fully-labelled test month exists and the dataset has enough labelled rows.
9. Evaluates the challenger with rolling chronological train/validation/test splits.
10. Promotes the challenger only if the configured quality gates pass; otherwise the current model stays live.
11. Reloads the in-process intelligence model cache after a successful promotion.

## Quality gates

Defaults:

- ROC-AUC >= 0.75
- Recall >= 0.70
- F1 may not fall by more than 0.03 vs the incumbent
- ROC-AUC may not fall by more than 0.03 vs the incumbent
- At least 1,000 fully-labelled project-month rows

These are configurable in `backend/.env`.

## Install the new dependencies

From the active LandGuard virtual environment:

```powershell
cd C:\LandGuard\backend
pip install -r requirements.txt
```

## One-time refresh after applying the patch

```powershell
cd C:\LandGuard\backend
python -m app.ml.build_paimana_panel
python -m app.ml.train_paimana
```

The training split is no longer hard-coded to 2025/2026. It rolls forward automatically using the latest fully-labelled monthly snapshot:

- latest labelled month = held-out test
- previous labelled month = validation/calibration
- all earlier labelled months = training

## Automatic monitoring

By default:

- enabled: yes
- first check: ~60 seconds after backend startup
- repeat interval: every 6 hours

Run normally:

```powershell
uvicorn app.main:app --reload
```

The background monitor will run without requiring a browser to remain open.

## System Admin dashboard

Open `/admin` as the SYSTEM_ADMIN. The new **PAIMANA source monitor** card shows:

- latest published source month
- latest downloaded month
- latest fully-labelled month
- longitudinal dataset size
- current model and temporal test month
- retraining state
- promotion/rejection result
- a **Check now** button for an immediate manual run

System admins still do not gain access to operational project data.

## Important safety behavior

New data does **not** directly replace the model.

The pipeline follows:

`new snapshot -> ingest -> wait for 3-month label maturity -> challenger training -> temporal validation -> quality gates -> promote/reject`

This prevents a newly downloaded month from blindly overwriting the working model.

## PAIMANA TLS note

The public PAIMANA host has previously presented certificate-validation problems to Python clients. The patch therefore has `PAIMANA_VERIFY_SSL=false` by default for this **public-data source only**. Set it to `true` once the official endpoint validates normally in your environment. Do not use this setting for authenticated/private systems.

## Recommended presentation wording

> LandGuard continuously monitors the public PAIMANA reporting source. When a new monthly snapshot is published, it ingests and validates the new project history. Because the prediction target has a three-month horizon, LandGuard waits until outcomes are mature before retraining. A challenger model is then evaluated on a new chronological holdout and promoted only if quality gates are satisfied; otherwise the incumbent model remains active.
