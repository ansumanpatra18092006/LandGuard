# Predictive Delay Outlook

This patch adds a second, conditional regression model alongside the existing PAIMANA schedule-slip classifier.

- Model 1: probability that the reported schedule moves later within the next 3 months.
- Model 2: conditional extension magnitude in days **if** a future schedule extension occurs.
- Delay exposure: calibrated slip probability × conditional extension days.

The duration target is derived from the same official monthly PAIMANA snapshots by comparing the current effective schedule date (revised date if already present, otherwise original date) with the maximum later effective schedule date observed in the next three reporting months. Revised/future dates are never model inputs.

The likely range is based on the 80th percentile absolute validation residual. It is an uncertainty band, not a guarantee.

## Apply
Extract over `C:\LandGuard`, then retrain:

```powershell
cd C:\LandGuard\backend
python -m app.ml.train_paimana
```

New artifacts:

- `model_artifacts/delay_duration_regressor.joblib`
- `model_artifacts/duration_metadata.json`

Then restart backend/frontend. No database migration is required.
