# LandGuard Final Governance Patch

This patch implements the three highest-value actions from the judge-level audit:

1. **Canonical model-ready Rayagada demo dataset** — one deterministic seed command now creates/refreshes eight explicitly fictional illustrative projects with coordinates, operational land-acquisition indicators and all PAIMANA model inputs. The supplied model produces LOW, MEDIUM and HIGH demonstration cases.
2. **Persisted Intervention Ledger** — officers can convert recommendations into assigned actions with owner, due date, priority and OPEN / IN PROGRESS / RESOLVED state. Every intervention change is written to an intervention-event trail.
3. **Transparent Acquisition Readiness** — a deterministic readiness score formalizes compensation, possession, R&R and administrative blockers. It is explicitly labelled rule-based decision support, not ML.

The dashboard War Room also shows tracked/overdue interventions, and the AI panel links directly to the Intervention Ledger.

## Apply

Extract this ZIP into `C:\LandGuard` and replace matching files.

Then:

```powershell
cd C:\LandGuard\backend
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
python -m app.db.verify_demo
```

Expected demo verifier shape:

```text
P-RGD-001   HIGH
P-RGD-003   LOW
P-RGD-007   MEDIUM
...
Demo verification passed: LOW, MEDIUM and HIGH predictive cases are available.
```

The exact probabilities can vary if you retrain the model, so the verifier checks the artifact that is actually deployed on your machine.

Start backend:

```powershell
uvicorn app.main:app --reload
```

Start frontend:

```powershell
cd C:\LandGuard\frontend
npm run dev
```

## What to demonstrate

### War Room

The District Risk Pulse now shows:
- predictive portfolio ranking;
- acquisition-readiness context;
- open tracked actions;
- overdue actions.

### Process Twin

The former Digital Twin label is now **Process Twin**. It adds a formal Acquisition Readiness card:
- readiness score / 100;
- BLOCKED / CONSTRAINED / READY;
- primary blocker;
- next milestone;
- component scores.

Methodology is displayed in the UI. It is a transparent prototype index, not a government standard and not ML.

### Intervention Ledger

Open a project → **Interventions**.

Create an action from the project's real recorded bottlenecks:
- action;
- owner;
- due date;
- priority.

Then move it:

`OPEN → IN PROGRESS → RESOLVED`

Each change appears in the intervention audit events. The War Room updates its tracked-action and overdue counts.

## Environment reproducibility

`requirements.txt` now pins:

```text
scikit-learn==1.9.1
```

because the deployed artifact was trained using that version. If you intentionally retrain under another version, update the pin and artifact together.

## Verification performed on this patch

Backend test suite:

```text
90 passed, 1 skipped
```

The single skip remains the opt-in live PostgreSQL integration test.
