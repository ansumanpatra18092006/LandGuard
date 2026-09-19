# LandGuard Advanced AI Refinement

This patch is designed to be extracted over the current LandGuard project after the Advanced AI patch.

## Changes

- Historical analogues now prefer same-sector PAIMANA projects first.
- Cross-sector analogues are used only as a labelled fallback when fewer than five same-sector projects are available.
- Similar-case API rows expose `same_sector` so the UI can explain the evidence set honestly.
- Scenario Lab now uses two model inputs:
  - hypothetical expenditure progress
  - assumed days to the original deadline
- Scenario controls initialise from the project's current values and reset correctly when changing projects.
- Scenario timing automatically keeps `original_deadline_passed` consistent with the assumed days-to-deadline.
- SHAP output no longer describes raw SHAP magnitudes as percentage points. The UI presents relative influence strength instead.

## Apply

Extract this ZIP directly into `C:\LandGuard` and allow replacement of matching files.

No migration and no retraining are required for these UI/inference refinements. Restart backend and frontend.

```powershell
cd C:\LandGuard\backend
uvicorn app.main:app --reload
```

```powershell
cd C:\LandGuard\frontend
npm run dev
```

## Scenario interpretation

The Scenario Lab is a model sensitivity tool, not a causal simulator. It answers:

> How would this already-trained model score a hypothetical project state with this expenditure progress and this amount of schedule pressure?

It does not claim that increasing expenditure or changing the passage of time will itself cause the predicted risk change.
