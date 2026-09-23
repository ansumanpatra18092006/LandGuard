# LandGuard AI — Consolidated README

LandGuard AI is a predictive and operational decision-support platform for land-acquisition delay intelligence. It combines:

- acquisition-specific operational indicators,
- a real PAIMANA-trained near-term schedule-slip model,
- transparent readiness / friction / bottleneck logic,
- GIS and portfolio analytics,
- a Process Twin and Delay Cascade,
- explainable AI and historical analogues,
- intervention tracking,
- policy-aware workflow automation,
- role-based governance and auditability,
- deployment on a React + FastAPI + PostgreSQL/PostGIS stack.

> **Core product idea:** move from **risk detection → explanation → prioritization → intervention → ownership → deadline → escalation → audit**.

---

## 1. Current Product Architecture

```text
React frontend
    ↓
FastAPI REST API
    ↓
PostgreSQL + PostGIS
    ↓
Operational intelligence + ML services
    ↓
Intervention / audit workflow
```

Production deployment keeps the React SPA and FastAPI API on the same origin. Supabase provides authentication and PostgreSQL/PostGIS; Brevo is used for invitation email delivery.

### Main technology stack

- **Frontend:** React + Vite
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **Spatial layer:** PostGIS
- **GIS UI:** Leaflet
- **Authentication:** Supabase
- **ML:** scikit-learn, XGBoost where available
- **Deployment:** Docker + Render
- **Email:** Brevo

---

# 2. Core Intelligence Layers

LandGuard deliberately separates three different kinds of evidence.

## A. Acquisition-specific operational intelligence

This is based on current land-acquisition records such as:

- compensation completion,
- possession,
- rehabilitation & resettlement progress,
- pending approvals,
- legal disputes,
- stakeholder-response delay,
- elapsed acquisition time,
- land area,
- affected families.

These power transparent operational metrics such as:

- Land-Acquisition Friction Index
- Acquisition Readiness
- Acquisition Delay Risk Index
- Primary Bottleneck
- Intervention Priority
- Process Twin
- Delay Cascade
- Automation triggers

These are **transparent decision-support rules / heuristics**, not ML probabilities.

## B. PAIMANA ML schedule signal

The current real trained ML baseline predicts:

> **Will the reported project completion schedule move to a later date within the next 3 reporting months?**

This is a **binary classification problem**.

The current model uses:

- project sector,
- original approved project cost,
- cumulative expenditure,
- days to original deadline,
- whether the deadline has already passed,
- expenditure / original-cost ratio.

It deliberately does **not** use land-acquisition operational fields such as compensation, possession, legal disputes or pending approvals, because those fields were not present in the PAIMANA training data.

## C. Acquisition-specific ML — research / next-stage pipeline

A second real-data path is being built from public Bhoomi Rashi and LACRRIS records.

The target is acquisition-stage delay rather than wider project schedule slippage.

This acquisition-specific ML pipeline is **experimental until data extraction, matching, validation and external quality checks are complete**.

---

# 3. Real PAIMANA ML Baseline

## Prediction target

For a project observed at month `T`:

```text
Will the reported effective completion schedule move later
within the next 3 reporting months?
```

Target:

```text
0 = no near-term schedule revision
1 = schedule moves later within 3 reporting months
```

## Source period

Official monthly PAIMANA snapshots:

```text
July 2025 → May 2026
```

## Temporal evaluation split

```text
Training:
2025-07 → 2025-12
5,420 rows

Validation:
2026-01
1,702 rows

Held-out test:
2026-02
1,948 rows
```

This is a **time-based holdout**, not ordinary random K-fold cross-validation.

The reason is that PAIMANA is longitudinal. Randomly mixing project-month observations can leak information from the same project across train and test.

## Candidate models

- Logistic Regression
- Random Forest
- Gradient Boosting
- XGBoost

Model selection used validation F1.

**Selected model:** Random Forest.

## Held-out test metrics

Current documented PAIMANA baseline:

```text
Accuracy:          0.8244
Balanced accuracy: 0.8303
Precision:         0.7593
Recall:            0.9078
F1:                0.8269
ROC-AUC:           0.9214
Confusion matrix:  [[789, 259],
                    [ 83, 817]]
```

These metrics describe the **PAIMANA schedule-slip baseline**. They are not validation of a production land-acquisition-specific model.

## Probability calibration

The PAIMANA classifier supports calibrated probabilities using a probability calibrator.

## SHAP

SHAP is used to explain the PAIMANA model locally.

SHAP answers:

> Which model inputs pushed this prediction upward or downward?

SHAP values are **not direct probability percentage points**.

## Historical analogues

Historical analogues prefer same-sector PAIMANA project states first.

Cross-sector analogues are only used as a labelled fallback when there are too few same-sector examples.

The displayed similarity score is a **feature-space similarity measure**, not a probability.

---

# 4. Continuous-Learning PAIMANA Pipeline

The PAIMANA ingestion / training pipeline supports monitored model refresh.

Flow:

```text
new PAIMANA snapshot
    ↓
ingest and validate
    ↓
wait until 3-month outcome is mature
    ↓
rebuild longitudinal dataset
    ↓
train challenger
    ↓
chronological validation
    ↓
quality gates
    ↓
promote or reject
```

Default quality gates:

```text
ROC-AUC >= 0.75
Recall >= 0.70
F1 may not fall by > 0.03 vs incumbent
ROC-AUC may not fall by > 0.03 vs incumbent
At least 1,000 fully labelled project-month rows
```

The latest labelled month is used as held-out test, the previous labelled month as validation/calibration, and all earlier labelled months as training.

For SIH demo deployment, automatic PAIMANA monitoring can be disabled to avoid unexpected retraining during presentation.

---

# 5. Conditional Delay-Duration Model

A second PAIMANA model estimates:

> **If a future schedule extension occurs, roughly how large might that extension be?**

This is a regression model.

Important:

- it is conditional on a slip occurring,
- it is a rough severity estimate,
- its uncertainty is wide,
- it should not be presented as an exact delay-day forecast.

The likely range is based on validation residuals and is an uncertainty band, not a guarantee.

> **Current presentation guidance:** emphasize the 3-month slip signal first. Treat extension magnitude as secondary evidence.

---

# 6. Land-Acquisition Operational Intelligence

## 6.1 Land-Acquisition Friction Index

Purpose:

> How much operational obstruction exists right now?

Inputs include:

- legal disputes,
- pending approvals,
- compensation gap,
- possession gap,
- R&R gap,
- stakeholder-response delay.

This is a deterministic operational index.

## 6.2 Acquisition Readiness

Purpose:

> How ready is the acquisition to progress toward handover?

Current readiness components:

```text
30% compensation progress
35% possession progress
15% R&R progress
20% administrative clearance
```

Administrative clearance is reduced by pending approvals and legal disputes.

The system classifies readiness as:

- READY
- CONSTRAINED
- BLOCKED

Readiness is explicitly **rule-based decision support, not ML**.

## 6.3 Acquisition Delay Risk Index

Current transparent prototype:

```text
50% acquisition friction
25% readiness gap
15% elapsed acquisition pressure
10% case-scale complexity
```

Case-scale complexity uses land area and affected families.

This is a **0–100 operational risk index**, not a probability.

## 6.4 Intervention Priority

The current UI refinement makes acquisition risk the base priority.

PAIMANA schedule evidence can **escalate** priority but cannot suppress a severe acquisition bottleneck.

Conceptually:

```text
base priority = acquisition risk

schedule escalation
= remaining headroom to 100
  × PAIMANA schedule signal
  × escalation factor
```

The result is an officer-prioritization heuristic, not a probability.

---

# 7. Process Twin and Delay Cascade

The Process Twin represents the acquisition workflow:

```text
Notification
→ Survey
→ Valuation / Award
→ Compensation
→ Rehabilitation
→ Possession
→ Handover
```

It overlays:

- current acquisition progress,
- readiness,
- primary blocker,
- next milestone,
- deterministic downstream dependency reasoning,
- independent PAIMANA schedule evidence.

The Delay Cascade is a **workflow heuristic**, not a causal ML model.

Example:

```text
Legal issue unresolved
→ compensation constrained
→ possession constrained
→ handover delayed
→ wider schedule pressure
```

---

# 8. Scenario / Intervention Simulator

The Scenario Lab is a **model sensitivity tool**, not a causal simulator.

For PAIMANA it varies model-sensitive inputs such as:

- hypothetical expenditure progress,
- assumed days to original deadline.

Administrative scenario controls operate in a separate lane.

They can affect:

- acquisition risk,
- friction,
- readiness,
- intervention priority,

but they do not change the PAIMANA ML probability unless a PAIMANA model input itself changes.

Correct interpretation:

> How would the already-trained model score a hypothetical project state?

Incorrect interpretation:

> This intervention will causally reduce delay probability by X%.

---

# 9. Policy-Aware Intervention Automation Engine

LandGuard automates administrative follow-up, not statutory decisions.

## Automatic triggers

Recorded project conditions can create workflow actions:

```text
legal dispute
→ Legal Review Required

pending approvals
→ Approval Clearance Required

low possession
→ Possession / Handover Review

low compensation
→ Compensation Follow-up

low R&R
→ R&R Follow-up

slow stakeholder response
→ Coordination Escalation

critical acquisition risk
→ High Acquisition-Risk Review
```

Each automated action can receive:

- owner,
- due date,
- priority,
- status,
- audit events.

Actions due soon receive a reminder event.

Overdue actions can be escalated to HIGH priority.

Cleared trigger conditions are recorded, but interventions are **not automatically resolved**.

An authorized officer must verify and close them.

LandGuard does **not** automatically:

- make legal determinations,
- approve compensation,
- transfer possession,
- clear disputes,
- close cases without officer verification.

Core governance principle:

> **AI recommends; authorized officials decide.**

---

# 10. Intervention Ledger

Interventions are persisted as accountable administrative actions.

Lifecycle:

```text
OPEN
→ IN PROGRESS
→ RESOLVED
```

Tracked fields include:

- action,
- owner,
- due date,
- priority,
- current status,
- creator,
- resolution note,
- event history.

Every intervention change is written to the audit trail.

---

# 11. Analytics Command Center

The Analytics page is designed as an acquisition-intelligence command center rather than a generic chart dashboard.

It includes:

- portfolio KPI strip,
- Acquisition Risk × Readiness matrix,
- dominant bottleneck ranking,
- acquisition-stage pipeline,
- generated portfolio insight,
- ranked priority-project queue,
- intervention health,
- compensation / possession / approval / dispute context,
- clear separation between acquisition indices and PAIMANA schedule signals.

No synthetic analytics metrics are introduced; the command center derives its values from existing dashboard, Risk Pulse and intervention APIs.

## Recharts sizing fix

The Risk × Readiness matrix uses explicit container measurement.

The chart renders only after the container reports positive width and height, preventing the Recharts `width(0) / height(0)` warning.

---

# 12. GIS

LandGuard uses Leaflet on the frontend and PostgreSQL/PostGIS for spatial storage/query support.

Current GIS is primarily **project-point based**.

It supports:

- project location mapping,
- risk / priority visualization,
- project inspection from the map,
- links to intelligence / intervention views.

Do not describe the current implementation as a full cadastral parcel-mapping system unless parcel geometry is actually integrated.

---

# 13. UX / Command Surfaces

The current product experience includes:

- Project Quick View,
- Command Palette,
- Scope Dock,
- Role Journey,
- Why LandGuard,
- Project Command Center,
- Analytics Command Center,
- Process Twin,
- AI Intelligence,
- Intervention Ledger,
- GIS,
- Officer Brief.

Quick View shows current acquisition-readiness context, including primary blocker and next milestone.

---

# 14. Role-Based Governance

## SYSTEM_ADMIN

Separate administration workspace.

Primary responsibilities:

- user management,
- invitation management,
- access oversight,
- audit visibility,
- pipeline / system monitoring.

System Admin should not gain operational project intelligence simply because they are an admin.

## Operational roles

- STATE_OFFICER
- DISTRICT_OFFICER
- IMPLEMENTING_AGENCY

These roles use the same operational interface but differ in backend-enforced scope and permissions.

Authentication determines **who the user is**.

Backend authorization determines **what they may access or modify**.

---

# 15. Canonical Demo Dataset

The SIH demo includes eight deterministic Rayagada project records.

They are explicitly:

```text
ILLUSTRATIVE / FICTIONAL DEVELOPMENT DATA
```

They include:

- coordinates,
- acquisition indicators,
- PAIMANA model baseline inputs,
- LOW / MEDIUM / HIGH demo cases.

Do not present these as real Rayagada government projects.

---

# 16. Bhoomi Rashi Acquisition-ML Pipeline

This is the strongest current path toward a **real acquisition-specific ML model**.

## Public-source strategy

The pipeline uses public Bhoomi Rashi detailed project reports and does not automate or bypass the CAPTCHA-protected search form.

The latest bulk acquisition result set contains a large set of public projects obtained through a legitimate portal search and exported for downstream processing.

## Notification-level extraction

The pipeline:

1. follows public 3A and 3D `View Details` links,
2. extracts notification information,
3. extracts village / survey-number information where available,
4. matches 3A and 3D records using overlapping geography,
5. rejects weak/unmatched pairs instead of force-pairing,
6. calculates 3A→3D stage duration,
7. creates a research delay label.

This is stronger than simply pairing the earliest project-level 3A with the earliest 3D.

## Current research target

```text
delay_over_365d
```

Interpretation:

```text
0 = matched 3A→3D stage <= 365 days
1 = matched 3A→3D stage > 365 days
```

This is a **research acquisition-stage delay label**.

It must **not** be described as a statutory-compliance classifier because court-stay periods and other legal exceptions are not reliably encoded in the public summary data.

## Candidate models

- Logistic Regression
- Random Forest
- Gradient Boosting

## Leakage control

Rows from the same project must stay together during validation.

The notification-level trainer uses grouped splitting by `project_id`.

Do not allow notification rows from the same project to appear in both train and test sets.

## Minimum data guidance

The current trainer refuses to train below 100 matched pairs.

Recommended:

```text
100 = hard minimum
500+ = meaningful prototype target
thousands = preferred
```

The model should only be treated seriously if both target classes are represented.

## Intended LandGuard use

After validation, the acquisition ML model can produce:

> **Acquisition-stage delay probability**

This would become the acquisition-specific predictive layer.

The existing operational fields still remain useful for readiness, friction, bottleneck detection and automation.

---

# 17. LACRRIS Acquisition-ML Research Path

LACRRIS is another potential acquisition-specific data source.

Public project reports can include:

- project / segment,
- Act,
- requiring body,
- district,
- rural / urban classification,
- land extent,
- SIA,
- preliminary notification,
- declaration / publication,
- award,
- payment,
- possession,
- family counts,
- compensation,
- R&R amounts.

Two exploratory derived targets were designed:

```text
declaration_over_12m
award_over_30m
```

These are **published evaluation-band-derived labels**, not universal statutory definitions.

The LACRRIS extraction path has been affected by public-site availability / timeout issues, so Bhoomi Rashi is currently the more practical acquisition-ML route.

---

# 18. How Bhoomi Rashi ML Will Map to LandGuard Project Inputs

LandGuard's project form contains richer fields than Bhoomi Rashi.

Current project inputs include:

- Project ID
- Project name
- Project type
- State
- District
- Acquisition stage
- Latitude / Longitude
- Land area
- Affected families
- Compensation %
- Possession %
- Rehabilitation %
- Pending approvals
- Legal disputes
- Stakeholder response days
- Elapsed acquisition days
- Original approved cost
- Cumulative expenditure
- Original completion date

Not all of these are available in Bhoomi Rashi training data.

Therefore the model must use a clearly defined shared feature contract.

### Acquisition ML features can include fields available in real historical acquisition data

Examples:

- project / road category,
- state / region,
- land area / land required,
- acquisition stage,
- elapsed stage time,
- earlier notification counts,
- previous-stage duration,
- land available / acquisition ratio,
- objection-related features where reliably extractable.

### Operational LandGuard-only fields remain in the rule-based layer

Examples:

- compensation %,
- possession %,
- R&R %,
- pending approvals,
- legal disputes,
- stakeholder response,
- affected families where unavailable in the chosen real training source.

### PAIMANA-only baseline fields remain in the schedule model

- original approved cost,
- cumulative expenditure,
- original completion date / deadline features.

The core rule is:

> **Prediction-time features must match the features used during training.**

---

# 19. Recommended Final Intelligence Hierarchy

The long-term LandGuard design is:

```text
REAL ACQUISITION HISTORY
Bhoomi Rashi / LACRRIS
        ↓
Acquisition-specific ML
        ↓
Acquisition-stage delay probability
        ↓
SHAP explanation
        │
        ├─────────────────────────────┐
        │                             │
CURRENT OPERATIONAL RECORD      PAIMANA HISTORY
        ↓                             ↓
Friction / Readiness             3-month schedule-slip ML
Bottleneck / Process Twin        wider-project evidence
        │                             │
        └──────────────┬──────────────┘
                       ↓
              Intervention Priority
                       ↓
              Automation Engine
                       ↓
        Owner → Due Date → Reminder
              → Escalation → Audit
```

---

# 20. Data Honesty Rules

LandGuard deliberately separates:

## Real data

- official PAIMANA monthly history,
- public Bhoomi Rashi / LACRRIS acquisition records where extracted.

## Derived values

- acquisition readiness,
- friction,
- acquisition delay risk index,
- intervention priority,
- process dependencies.

## Illustrative data

- canonical Rayagada demo project records.

Never present illustrative Rayagada records as government observations.

Never present a transparent index as a trained probability.

Never describe PAIMANA as directly trained on compensation, possession, disputes, R&R or approvals.

---

# 21. Local Development

## Backend

```powershell
cd C:\LandGuard\backend
C:\LandGuard\.venv\Scripts\activate
uvicorn app.main:app --reload
```

## Frontend

```powershell
cd C:\LandGuard\frontend
npm run dev
```

## Production build check

```powershell
cd C:\LandGuard\frontend
npm ci
npm run build
```

---

# 22. Database / Migration / Demo Seed

Typical setup:

```powershell
cd C:\LandGuard\backend
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
python -m app.db.verify_demo
```

The project pins the scikit-learn version used by the deployed artifacts.

If you intentionally retrain under a different version, update the version pin and artifacts together.

---

# 23. PAIMANA Training

Rebuild / retrain:

```powershell
cd C:\LandGuard\backend
python -m app.ml.build_paimana_panel
python -m app.ml.train_paimana
```

Typical generated artifacts include:

```text
backend/model_artifacts/classifier.joblib
backend/model_artifacts/probability_calibrator.joblib
backend/model_artifacts/metadata.json
backend/model_artifacts/model_comparison.json
backend/model_artifacts/delay_duration_regressor.joblib
backend/model_artifacts/duration_metadata.json
```

---

# 24. Bhoomi Rashi Notification-Level Pipeline

Activate the acquisition-data environment:

```powershell
cd C:\LandGuard
.\.lacrris-venv\Scripts\activate
```

Extract project / notification records:

```powershell
python bhoomirashi_notification_extract_resume.py `
  --input bhoomirashi_1745_seed_urls.csv `
  --projects-out bhoomirashi_projects.csv `
  --notifications-out bhoomirashi_notifications.csv `
  --delay 0.4 `
  --detail-delay 0.25
```

The resume-safe extractor checkpoints completed project IDs so interrupted runs can continue without reprocessing completed projects.

Then pair notifications:

```powershell
python match_3A_3D_notifications.py
```

Check matched rows and class balance:

```powershell
python -c "import pandas as pd; d=pd.read_csv('bhoomirashi_notification_pairs.csv'); print('Matched rows:',len(d)); print(d['delay_over_365d'].value_counts(dropna=False))"
```

Train only after the dataset is large enough and contains both classes:

```powershell
python train_notification_level_model.py
```

---

# 25. Render Deployment

Production architecture:

```text
Render Web Service
├── React production build
└── FastAPI

Supabase
├── Auth
└── PostgreSQL / PostGIS

Brevo
└── invitation email
```

Required environment variables include:

```text
DATABASE_URL
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
BREVO_API_KEY
BREVO_SENDER_EMAIL
PUBLIC_APP_URL
FRONTEND_ORIGIN
```

Keep secrets out of Git.

Use a persistent PostgreSQL database in production.

Startup flow:

```text
alembic upgrade head
    ↓
optional demo seed
    ↓
uvicorn
```

Health endpoint:

```text
/api/v1/health
```

---

# 26. Demo Flow

Recommended SIH demo:

```text
District Officer login
    ↓
War Room / Analytics
    ↓
Top-priority project
    ↓
Project Quick View
    ↓
Process Twin
    ↓
Acquisition Risk + Readiness + Bottleneck
    ↓
PAIMANA 3-month schedule signal
    ↓
SHAP + Historical Analogues
    ↓
Scenario / Intervention Simulator
    ↓
Automation-created Intervention
    ↓
Intervention Ledger
    ↓
Owner + Due Date + Status + Audit
    ↓
Officer Brief
    ↓
GIS
```

System Admin can be shown separately for:

- user management,
- invitations,
- access / audit,
- pipeline monitoring.

---

# 27. Recommended Presentation Language

## Main product line

> **LandGuard does not stop at predicting risk. It explains the bottleneck, prioritizes the case, converts qualifying conditions into accountable interventions, assigns an owner and deadline, and preserves an audit trail while keeping the authorized officer in control.**

## AI explanation

> **The current real ML baseline uses longitudinal PAIMANA history to predict whether the wider project schedule may move later within the next three reporting months. Acquisition-specific operational indicators remain transparent and separate. A dedicated acquisition-stage ML model is being built from public Bhoomi Rashi / LACRRIS histories.**

## Automation explanation

> **LandGuard automates administrative follow-up and accountability, not statutory decision-making.**

## Process Twin explanation

> **The Process Twin shows where acquisition currently stands, what is blocking the next milestone, and what downstream stages may be affected.**

## GIS explanation

> **GIS connects project location with risk, readiness and intervention priority for spatial monitoring.**

---

# 28. Current Limitations

- PAIMANA predicts wider schedule movement, not direct acquisition delay.
- Acquisition-specific ML is still experimental until the Bhoomi Rashi / LACRRIS dataset is fully extracted and validated.
- Current Rayagada project records are illustrative demo data.
- GIS is project-point based rather than full cadastral parcel mapping.
- Acquisition indices are transparent expert-prior / deterministic decision-support logic, not government standards.
- Scenario analysis is sensitivity analysis, not causal estimation.
- Conditional extension-day estimates have wide uncertainty.
- Public government data portals may be incomplete, inconsistent or temporarily unavailable.

---

# 29. Future Scope

- validated acquisition-specific ML from real longitudinal records,
- stage-wise acquisition-delay probabilities,
- richer objection / litigation / compensation history,
- integration with departmental systems,
- cadastral parcel GIS,
- automatic document ingestion,
- mobile officer workflow,
- multilingual interface,
- external validation across states,
- monitored acquisition-model retraining,
- stronger intervention-effect evaluation.

---

# 30. What Is Current vs Superseded / Experimental

This README consolidates multiple patches created at different stages of the project.

The current interpretation should be:

### Current / active concepts

- PAIMANA 3-month schedule-slip classifier
- acquisition readiness
- acquisition friction / delay-risk index
- intervention priority
- Process Twin
- Delay Cascade
- SHAP for PAIMANA
- historical analogues
- GIS
- Intervention Ledger
- policy-aware automation
- analytics command center
- role-based governance
- Render deployment

### De-emphasized

- exact delay-duration predictions
- expected-delay-exposure style headline metrics

These may still exist in older patch documentation or code, but should not be the main presentation story because duration uncertainty is wide.

### Experimental / research

- Bhoomi Rashi acquisition-specific ML
- LACRRIS acquisition-specific ML
- stage-wise real acquisition-delay probability

---

# 31. Core One-Line Summary

> **LandGuard combines real-data schedule intelligence, transparent acquisition-process reasoning, explainable evidence, GIS and human-authorized workflow automation to turn land-acquisition risk into accountable administrative action.**

## GIS cadastral / land-record workflow

LandGuard supports parcel-level cadastral overlays, but it deliberately **does not fabricate parcel geometry or infer legal ownership from imagery**.

- Bhuvan remains thematic/geospatial context only (`GET /api/v1/gis/bhuvan/config`).
- Odisha BhuNaksha and Bhulekh are exposed in the GIS UI as official reference/validation portals (`GET /api/v1/gis/land-records/config`).
- Parcel geometry must be imported from a real cadastral export as WGS84 / EPSG:4326 GeoJSON.
- Ownership is read only from supplied source attributes such as `ownership_type`; missing ownership stays `UNKNOWN`.
- Supported classes: `GOVERNMENT`, `PRIVATE`, `GOVERNMENT_LEASEHOLD`, `INSTITUTIONAL`, `UNKNOWN`.
- The GIS distinguishes `AUTHORITY_VERIFIED`, `IMPORTED_DATASET`, and `UNAVAILABLE` states.
- The seed process creates **no cadastral ownership polygons**. Migration `0007_remove_synthetic_cadastral_data` removes the old rectangular demo parcels from existing databases.
- The GIS page can import/replace a selected project's cadastral GeoJSON, remove it, render true source geometry, and calculate parcel areas when the file omits acreage.

Recommended GeoJSON properties are `plot_no`, `khata_no`, `unique_plot_id`, `ownership_type`, `kisam`, `village`, `tahasil`, and optional `area_acres`. Mark a file as authority-verified only when its provenance has actually been confirmed by the competent land-record authority.

After pulling this version into an existing database, run:

```powershell
cd backend
python -m app.db.init_db
python -m app.db.seed
```

`init_db` applies migration `0007`, which deletes only the old `ILLUSTRATIVE_SIH_DEMO` / `DEMO-*` ownership rows. Your project records are preserved.

---

## SIH 25017 compliance pass (v8)

The latest build adds the requirements that were missing or weak against the supplied SIH problem statement:

- persisted project-field audit events and historical snapshots,
- district/state historical delay-risk trend analytics,
- seven-stage acquisition lifecycle delay outlook,
- predictive model alerts in the Notice Center,
- GIS risk-intensity overlay for high-risk projects,
- bulk REST integration endpoint for external land-acquisition systems,
- integrated-record provenance,
- near-real-time dashboard refresh,
- audit events for cadastral dataset import/removal.

See `SIH_REQUIREMENTS_COVERAGE.md` for the requirement-by-requirement matrix and the remaining evidence/deployment dependencies that the prototype must not overclaim.
