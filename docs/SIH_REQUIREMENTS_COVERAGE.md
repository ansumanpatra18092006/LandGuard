# LandGuard — SIH 25017 Requirements Coverage

Source: **Predictive Analytics System for Early Detection of Land Acquisition Delays** (problem statement 25017).

## Coverage after the v8 compliance pass

| Requirement | LandGuard implementation | Status |
|---|---|---|
| AI/ML forecasting of land-acquisition delays | PAIMANA longitudinal schedule-risk model plus experimental Bhoomi Rashi acquisition-stage model | Implemented |
| Automatic identification of high-delay-risk projects | Portfolio risk pulse, priority queue and predictive alerts | Implemented |
| Project-wise risk score and prioritization | Evidence-adjusted ML delay probability plus transparent acquisition-friction/risk lane | Implemented |
| Key delay drivers | Explainability/feature contribution summaries, risk drivers, stage/watchout cards | Implemented |
| Explainable AI | Model explanation, similar cases, evidence/provenance and confidence labels | Implemented |
| Delay outlook across acquisition stages | Seven-stage lifecycle outlook for Notification → Completed | Implemented as transparent screening; calibrated stage-specific ML probability remains data-dependent |
| Interactive dashboards | Delay probability, categories, KPIs, stage comparison, district comparison, comparative analytics | Implemented |
| District/state delay trends | Persisted project snapshots and district/state historical trend charts | Implemented |
| Timeline analysis | Project history snapshots, audit events and schedule-risk timeline context | Implemented |
| GIS visualization of high-risk projects | Leaflet project map with risk markers and risk-intensity/heat overlay | Implemented |
| Automated alerts/notifications | Predictive delay alerts plus intervention/operational alerts in Notice Center | Implemented; external SMS/push gateways require credentials/provider |
| Predictive corrective recommendations | Project-level recommendations and intervention suggestions | Implemented |
| Continuous model learning | Monitoring/retraining/challenger pipeline with quality gates | Implemented; retraining quality depends on new labelled observations |
| APIs for existing systems/government databases | REST API plus bulk project upsert/capabilities integration endpoints | Implemented; actual government connections require official API/database access |
| Secure role-based access | System, state, district and implementing-agency scopes with protected endpoints | Implemented |
| Comprehensive audit trails | Authentication/audit trail, intervention ledger, project-field change audit and historical snapshots | Implemented |
| Real/near-real-time dashboard refresh | Mutation-triggered refresh plus periodic 60-second dashboard refresh | Implemented |
| PostgreSQL/PostGIS + GIS platform | PostgreSQL/PostGIS-ready backend and Leaflet GIS | Implemented |
| Nationwide scalability | State/district-scoped data model and integration APIs are nationwide-compatible | Architecture-ready; production nationwide deployment/load testing remains external |

## Important evidence boundary

LandGuard deliberately does **not** label heuristic stage screening as a calibrated ML probability. Training and validating a separate probability model for every acquisition lifecycle stage requires authoritative historical observations containing stage-entry dates, stage outcomes/delays and labels. The software now exposes the lifecycle feature and API so an official labelled dataset can replace/upgrade the screening estimator without changing the officer workflow.

Likewise, LandGuard now provides integration APIs and cadastral import interfaces, but it cannot create credentials or invent live access to Bhulekh/BhuNaksha, central/state land-acquisition databases, court systems, SMS gateways or government cloud environments. Those require authorization from the corresponding authority.

## New in v8 compliance pass

- Persisted project-field audit events.
- Historical project snapshots used for district/state trend analytics.
- Seven-stage acquisition lifecycle delay outlook.
- Predictive model alerts in the Notice Center.
- GIS risk-intensity overlay.
- External-system bulk project integration REST API.
- Integrated-record provenance classification.
- Near-real-time dashboard refresh.
- Cadastral import/removal audit events.
