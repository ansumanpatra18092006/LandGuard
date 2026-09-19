# LandGuard Acquisition-Aware Priority Patch

This patch closes the largest remaining judge-facing gap identified in the audit: the PAIMANA ML signal does not use land-acquisition operational variables. LandGuard now keeps the evidence lanes separate and combines them transparently only for administrative prioritisation.

## Added

- **Land-Acquisition Friction Index** (rule-based, not ML)
  - 20% legal disputes
  - 15% pending approvals
  - 20% compensation gap
  - 20% possession gap
  - 10% rehabilitation/R&R gap
  - 15% stakeholder-response delay
- **Acquisition-aware intervention priority**
  - 35% PAIMANA schedule signal
  - 45% Land-Acquisition Friction
  - 20% acquisition-readiness gap
- War Room now ranks by intervention priority instead of expected delay exposure alone.
- Full-screen simulator now allows administrative actions to reduce friction / improve readiness while keeping ML probability separate.
- AI panel now includes a model-evidence card explicitly stating that acquisition factors are not ML inputs.
- Auto PAIMANA monitoring defaults to OFF for a stable demo. It can still be enabled in deployment with `PAIMANA_AUTO_MONITOR_ENABLED=true`.

## Important wording

The Friction Index and Intervention Priority are transparent prototype decision-support heuristics. They are **not ML probabilities**, **not government-standard scores**, and **not causal estimates**.

The PAIMANA model remains a central-infrastructure schedule-slip early-warning baseline. Compensation, possession, R&R, approvals, legal disputes and response time remain a separate operational evidence lane.

## Verification

Backend suite after this patch: **92 passed, 1 skipped**.
