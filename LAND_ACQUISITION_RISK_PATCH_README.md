# LandGuard — Land-Acquisition Risk Alignment Patch

This patch adds a land-acquisition-specific risk layer so LandGuard no longer presents the PAIMANA schedule model as the primary answer to the SIH problem.

## New primary signal

**Acquisition Delay Risk Index (0–100)**

It is a transparent prototype decision-support index, not a trained probability. It uses:
- 50% recorded acquisition friction
- 25% acquisition-readiness gap
- 15% elapsed-acquisition pressure
- 10% case-scale complexity (land area + affected families)

The friction component itself uses legal disputes, pending approvals, compensation gap, possession gap, R&R gap, and stakeholder response delay.

## Separation of evidence

- PAIMANA ML => future schedule-slip signal for infrastructure projects.
- Acquisition Delay Risk => land-acquisition-specific operational risk index.
- Intervention Priority => 70% Acquisition Delay Risk + 30% PAIMANA schedule signal.

This keeps the solution aligned to the problem statement without pretending that PAIMANA trained on acquisition outcomes.

## Scenario behavior

Administrative actions now change:
- acquisition delay risk
- friction
- readiness
- intervention priority

They do **not** change the PAIMANA ML probability unless the separate model-sensitivity inputs are changed.

## Verification

Backend: 92 passed, 1 skipped in the build environment.
Frontend production build was not run because node_modules is intentionally absent from the clean source tree.
