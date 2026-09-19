# LandGuard — Intelligence Priority & UI Refinement Patch

Built from the uploaded `LandGuard_clean(4).zip`.

## What changed

- Acquisition Delay Risk now establishes the base intervention priority.
- PAIMANA schedule evidence can only escalate priority; it cannot suppress a high land-acquisition risk case.
- Primary blocker and current-stage action text are now aligned.
- The AI Intelligence page now leads with Acquisition Delay Risk, Intervention Priority, Readiness, and Primary Bottleneck.
- PAIMANA is visually separated as independent supporting ML evidence.
- High-detail methodology, model evidence, and delay-duration uncertainty moved into progressive disclosure.
- The rough extension-days estimate is de-emphasized because its uncertainty is wide.
- SHAP now explicitly explains the PAIMANA schedule signal, not the acquisition-risk index.
- Historical analogue wording now uses `Similarity score 0.xx`, not a probability-like `% similar`.
- War Room copy now explains the escalation-only role of PAIMANA schedule evidence.

## Priority logic

`final priority = acquisition risk + schedule escalation`

where:

`schedule escalation = remaining headroom to 100 × PAIMANA schedule signal × 30%`

The result is a transparent officer-prioritization heuristic, not a probability.

## Verification

Backend: **93 passed, 1 skipped**.

The sandbox runtime has scikit-learn 1.8 while the shipped model artifact was trained with 1.9.1, so artifact-loading warnings appear here. Your project requirements already pin 1.9.1.

A full Vite build could not be completed in the sandbox because dependency installation timed out and left an incomplete `node_modules`. Run locally:

```powershell
cd C:\LandGuard\frontend
npm ci
npm run build
```

Then smoke-test AI Intelligence and the full-screen Intervention Simulator before the demo.
