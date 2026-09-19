# LandGuard AI

Predictive Land Acquisition Delay Intelligence System — operational analytics prototype for the supplied SIH 2026 brief (SIH26017).

**AI recommends; authorized officials decide. Current model artifacts use illustrative synthetic data, not validated government outcomes.**

The original presentation and handbook are preserved planning materials, not evidence of implemented government integrations.

## Current implementation

Reviewed against the current files on 16 September 2026. Later sections retain phase-specific setup and implementation history; this section supersedes earlier claims that authentication, GIS previews, and a model pipeline do not exist.

- Public entry: `/` explains the product and intended users; `/access` explains invitation-only enrollment; `/login` accepts a real Supabase email/password. `/accept-invitation` activates invited accounts. Administrators manage invitations at `/admin/users`.
- Workspace: `/dashboard` provides operational KPIs, bottlenecks and the project queue; `/analytics` provides district comparisons and stage distributions; `/projects` manages individual records. Filters carry between these views.
- GIS now uses an embedded Leaflet + OpenStreetMap basemap with synchronized project markers, filters, viewport context, fit-to-project controls, and scoped project drill-down. A model training/inference pipeline, synthetic model artifact, explanation methods, rule recommendations, and operational alert endpoint now exist. Synthetic results are not evidence of predictive validity on real acquisition projects.
- Authentication now uses Supabase Auth, protected role profiles, hashed server sessions in HttpOnly cookies, CSRF checks, rate limiting and Brevo invitations. Project reads, writes, aggregates, maps and predictions enforce assigned jurisdiction. The demo login has been removed. **Cloud setup is required:** follow [real account setup](backend/supabase/README.md). MFA, SSO and self-service password recovery remain unimplemented.
- Current backend verification: **79 passed, 1 PostgreSQL integration test skipped**. Identity tests use isolated Supabase/Brevo provider fixtures and verify session revocation, invitation activation, CSRF, rate limiting and jurisdiction enforcement. Existing synthetic model artifacts still emit dependency-version warnings. Hosted Supabase SQL and real email delivery require live verification after configuration.
- Current frontend verification: `npm run build` and `node identity-smoke.cjs` pass. The identity browser suite uses isolated API fixtures, covers account administration, login/logout, invitation activation and expired links, and checks desktop/mobile layout. `product-smoke.cjs` and `experience-smoke.cjs` now require `LANDGUARD_TEST_EMAIL` and `LANDGUARD_TEST_PASSWORD` for a real activated test account; no default credentials remain in those scripts.

### Real account setup

Run `backend/supabase/001_identity.sql` in your Supabase SQL Editor, fill `backend/.env` with your Supabase server key and Brevo key/verified sender, then provision the first administrator using `python -m app.db.bootstrap_admin --email YOUR_EMAIL --name YOUR_NAME` from `backend`. The email invitation lets that person choose their own password. Full commands and deployment guidance: [Supabase + Brevo setup](backend/supabase/README.md). No live email delivery has been verified without those settings.

### Intended users and secure enrollment design

The public entry now contains an interactive walkthrough with three clearly fictional `EX-*` records, clickable approval filters, district comparisons, and inline record inspection. These examples never call the project API. Role choices explain a proposed journey and carry a destination to login; they do not assign privileges.

The login page adds password visibility, Caps Lock feedback, field focus guidance, disabled duplicate submission, and inline error feedback. Workspace routes have restrained entrance transitions and a selection bar that links filtered analysis to records. Refresh retains the previous records while fetching the same scope; changing filters still clears stale-scope data. Reduced-motion preferences disable motion throughout.

Run `node experience-smoke.cjs` for the walkthrough, role choices, login errors and controls, route motion, selection context, refresh continuity, responsive layout, and reduced-motion checks. It uses the same required test-credential environment variables as `product-smoke.cjs`.

State officers oversee a state portfolio; district officers review local acquisition work; implementing agencies maintain assigned projects; administrators manage approved identities and assignments. Landowners and citizens are stakeholders, but the administrative portal is not a public compensation or land-claim submission service.

For an institutional rollout, use **invitation or administrator-approved enrollment**. Verify the work identity and department/agency relationship; administrators assign role and state/district/project memberships. A work-email domain alone is insufficient and applicants must not self-assign elevated privileges. Invitations must expire and be single-use. Prefer an approved organization identity provider using OIDC, with MFA; local accounts need individual password hashes, recovery, rate limiting, and account lifecycle management.

Serve over HTTPS, use revocable sessions in Secure/HttpOnly/SameSite cookies with CSRF protection, and enforce authorization at every API and database query. Check both action permissions and jurisdiction/assignment, including list queries, aggregates, maps, alerts, and direct project IDs. Record administrative changes, suspend accounts, and revoke sessions when assignments change. These are required next-phase controls, not features supplied by the landing page.

References: [OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), and [session management guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

### Earlier foundation phase

- React, Vite, React Router and Recharts: operational dashboard, three charts, district progress table, filtered/paginated project registry, details and create/edit/delete forms.
- FastAPI, Pydantic and SQLAlchemy 2: validated persistent project CRUD and SQL-backed analytics.
- PostgreSQL is the intended database, configured through `DATABASE_URL`. SQLite remains an explicit local fallback and the default automated test database.
- Alembic versions the original Project schema and prepares PostGIS point locations.
- Twelve explicitly fictional illustrative seed records cover six districts, multiple project types and stages. Re-running seed inserts only missing IDs and preserves existing edits.
- Operational thresholds are configurable and labeled as proposed prototype rules. They are not delay predictions or SHAP/model factors.
- No ML training, predictions, SHAP, recommendations, authentication/RBAC, alerts, Leaflet, GeoServer or government integrations in this phase. Keep this unauthenticated prototype local until access controls are implemented.

## Architecture

Browser → React API client → FastAPI routes → SQLAlchemy aggregate/project queries → PostgreSQL + PostGIS.

```text
backend/
  alembic.ini
  alembic/env.py                     shared configuration and model metadata
  alembic/versions/0001_projects.py   frozen original schema
  alembic/versions/0002_postgis.py    PostGIS extension and location view
  alembic/versions/0003_gis_spatial_index.py  GiST spatial index for project points
  app/api/filters.py                 common project/dashboard filters
  app/api/routes/projects.py         existing CRUD
  app/api/routes/dashboard.py        dashboard endpoints
  app/schemas/dashboard.py           typed analytics responses
  app/services/dashboard_service.py SQL aggregation and operational indicators
  app/db/init_db.py                  migration entrypoint and legacy adoption
  app/db/verify_postgres.py          opt-in isolated integration verification
  tests/                            CRUD, analytics, migration and integration tests
frontend/src/
  pages/Projects.jsx                 dashboard/registry orchestration
  pages/ProjectDetails.jsx           project observations and future map area
  components/dashboard/             lazy-loaded analytics and Recharts
  components/projects/              reusable filters and project table
  services/api.js                    REST and error handling
  services/dashboard.js              centralized analytics requests
```

The Project model/API fields are preserved. Prototype project types and stages remain the validated existing values (including VALUATION); these are not claimed as official government taxonomies. No delayed-outcome field has been added without a defined labeling policy.

## PostgreSQL setup

Prerequisites: Python 3.11+, Node.js 20.19+ or 22.12+, and PostgreSQL with PostGIS (or Docker Desktop).

From PowerShell in `C:\LandGuard`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
# Edit POSTGRES_PASSWORD in root .env before starting the database.
docker compose up -d db
Copy-Item backend\.env.example backend\.env
# Edit DATABASE_URL to match your local PostgreSQL user/password/database.
cd backend
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\python.exe -m app.db.seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The expected URL is `postgresql+psycopg://user:password@localhost:5432/landguard`. Use your own credentials; URL-encode special characters in passwords. The examples are local development placeholders, not production credentials. The Docker database port binds to loopback only.

For an existing PostgreSQL server, skip Docker and set `DATABASE_URL` directly. The migration user needs table/view creation permissions and permission to enable PostGIS, or a DBA must pre-enable it. The Python package alone does not install the server-side PostGIS extension. Database migration failures are not silently replaced with SQLite.

The backend always loads `backend/.env`; environment variables override it. Without either setting, it explicitly falls back to the absolute `backend/landguard.db` SQLite file. A relative SQLite URL in the environment is relative to the working directory; run backend commands from `backend`.

## PostGIS support

Migration `0002_postgis` enables PostGIS in the public schema and creates the PostgreSQL-only `project_locations` view. It exposes `id`, `project_id`, `state`, `district`, and `location` as a Point geometry in SRID 4326, derived from `longitude, latitude` in that order.

This live view always follows coordinate edits and deletions, without triggers or duplicate stored coordinates. Migration `0003_gis_spatial_index` adds a GiST expression index over the same SRID 4326 point expression, so PostgreSQL/PostGIS can accelerate spatial viewport queries without duplicating coordinates. SQLite skips PostgreSQL-only spatial objects while retaining latitude/longitude fallbacks for tests.

Verify from the repository root:

```powershell
docker compose exec db psql -U landguard -d landguard -c "SELECT PostGIS_Version();"
docker compose exec db psql -U landguard -d landguard -c "SELECT project_id, ST_AsText(location), ST_SRID(location) FROM project_locations LIMIT 5;"
```

Downgrading the spatial revision removes the view, not the potentially shared PostGIS extension. Downgrading the initial revision removes the projects table and its data; use downgrades only with an appropriate backup.

## GIS workspace

The operational `/map` route now uses Leaflet 1.9.4 with OpenStreetMap raster tiles. It provides state/district/stage/search filters, project marker selection, fit-to-project controls, browser geolocation, operational marker context, project drill-down, and responsive mobile behavior. Marker data is still permission-scoped by the FastAPI backend, so a district officer cannot obtain markers outside their assigned district simply by changing frontend filters.

`GET /api/v1/map-data` also supports optional spatial parameters:

- `min_lat`, `max_lat`, `min_lon`, `max_lon` for a bounding box. PostgreSQL uses PostGIS `ST_Intersects`; SQLite uses latitude/longitude range fallback for tests.
- `near_lat`, `near_lon`, `radius_km` for radius lookup. PostgreSQL filters with `ST_DistanceSphere`; SQLite uses a Haversine fallback.

After applying this patch run `alembic upgrade head` so the GiST spatial index is created in Supabase/PostgreSQL.

## Alembic and existing databases

Run from `backend`:

```powershell
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\alembic.exe current
..\.venv\Scripts\alembic.exe check
..\.venv\Scripts\alembic.exe revision --autogenerate -m "description"
```

Review generated revisions before applying them. Alembic uses the same settings and SQLAlchemy metadata as the application. The initial migration is a frozen schema snapshot; importing the live model into historical migrations would make old revisions change over time. Extension-owned PostGIS tables are excluded from autogeneration; the spatial view is managed explicitly by its revision.

The previous prototype used `create_all` without version tracking. For that existing SQLite database, stop the backend, make a backup, then run:

```powershell
Copy-Item landguard.db landguard.before-migrations.db
..\.venv\Scripts\python.exe -m app.db.init_db --adopt-legacy
..\.venv\Scripts\python.exe -m app.db.seed
```

Legacy adoption compares metadata and check constraints before stamping the original revision; it rejects schema drift. It does not blindly stamp an arbitrary database. PostgreSQL legacy adoption requires manual schema review before stamping `0001_projects`, because PostgreSQL normalizes constraint expressions. Fresh databases use `alembic upgrade head` normally.

The local demo was backed up as `backend/landguard.pre-alembic.db`, adopted successfully, and extended to twelve illustrative projects. Both database files are ignored by Git. Changing the URL does not transfer SQLite records into PostgreSQL.

## Frontend startup

### Interface design and verification

The frontend uses a shared forest/teal and slate design system in `frontend/src/tokens.css`. It uses the system sans-serif stack, with no remote font request or new UI framework. Shared cards, buttons, progress bars, badges, skeletons and focus styles use these tokens.

The shell now offers a collapsible desktop sidebar, native modal navigation drawer on mobile, global project search, page context, and explicit demo/profile and notification status. Dashboard, Projects and Analytics are working routes. GIS Map and Settings remain coming soon. Review notices open an interactive prototype inbox based on current database observations.

The dashboard pairs a compensation/possession comparison chart with an Administrative Bottlenecks card, followed by district and stage charts. All inputs remain API-backed; bottleneck percentages are derived from returned project counts, not invented trends. Detailed district figures are expandable. Project filters are URL-backed and collapsible, with removable chips and a clear action. Desktop project tables have sticky headers and a visible details action; mobile uses project cards with progress and administrative observations.

Project details now group metadata, land/family/duration information, progress and administrative counts into a command-center layout. The three-part AI intelligence panel and geographic map area are explicitly unavailable placeholders. No prediction, map, alert or authentication functionality has been fabricated.

New files: `components/layout/AppShell.jsx`, `components/dashboard/ProgressComparison.jsx`, `components/dashboard/BottleneckCard.jsx`, `components/projects/IntelligencePanel.jsx`, `tokens.css` (all under `frontend/src`), and `frontend/ui-smoke.cjs`.

Modified frontend files: `App.jsx`, `components/common.jsx`, `pages/Projects.jsx`, `pages/ProjectDetails.jsx`, `pages/ProjectForm.jsx`, `components/dashboard/DashboardAnalytics.jsx`, `components/dashboard/DistributionChart.jsx`, `components/projects/ProjectFilters.jsx`, `components/projects/ProjectTable.jsx`, `services/api.js`, `styles.css`, and `dashboard.css`. The existing browser smoke scripts and this README were updated. The interaction phase below extends the filtering and district-summary contracts.

Accessibility includes a skip link, native focus containment/Escape handling in the mobile dialog, restored opener focus, semantic table headings/captions, labeled form controls, screen-reader progress labels, focus-visible styles, keyboard-readable metric explanations and reduced-motion support. Errors from the server are mapped to safe, useful messages instead of exposing raw response text.

`node ui-smoke.cjs` checks dashboard, details and form layouts at **1440, 1280, 1024, 768, 430 and 390 pixels**, chart dimensions, global search, all filter types, chips, pagination, desktop collapse, mobile navigation/focus, planned features and the unknown-route state. The existing dashboard/CRUD suites also verify loading, empty results, safe error/retry behavior and create/edit/delete persistence. Screenshots use ignored `*-smoke.png` files. All three suites passed; the viewport suite reported no browser JavaScript errors or warnings.

### Commands

In a second terminal:

```powershell
cd C:\LandGuard\frontend
npm ci
npm run dev -- --strictPort
```

Open [the dashboard](http://127.0.0.1:5173) and [API documentation](http://127.0.0.1:8000/docs). Vite proxies `/api` to port 8000 for development. A hosted frontend or build preview requires `VITE_API_URL` and a matching backend `FRONTEND_ORIGIN`, or a reverse proxy; preview does not use the development proxy. Chart code loads separately from the registry/detail interface.

For a local demo without PostgreSQL, leave PostgreSQL settings unset (or explicitly choose SQLite), run `python -m app.db.init_db` using the virtual environment and seed it before starting the backend.

## APIs and analytics semantics

Existing endpoints under `/api/v1` are preserved:

- `GET /health`: database connectivity and explicit untrained-model status.
- `GET /projects`: `{items,total,page,page_size}`; page starts at 1 and page size is 1–100.
- `POST /projects`: validated creation (201), duplicate ID (409), invalid input (422).
- `GET /projects/{project_id}`, `PUT /projects/{project_id}`, `DELETE /projects/{project_id}`: detail, full update and permanent delete (204); missing records return 404.

New endpoints:

- `GET /review-notices?limit=20`: current projects with pending approvals or disputes, ordered by record update time, with a 1–100 row limit. Prototype observations, not an alert event stream.
- `GET /dashboard/summary`: total projects, sum of pending approvals, number of projects with disputes, unweighted average compensation, provenance counts. `high_risk`, `medium_risk`, `low_risk` are **null**, not zero-valued model results.
- `GET /dashboard/district-summary`: grouped by **state and district**, with project count, compensation/possession averages, sums of approvals and disputes, and counts of projects with each condition.
- `GET /dashboard/stage-distribution`: database counts by acquisition stage.
- `GET /dashboard/operational-risks`: **Operational indicators**, counting projects with disputes, approvals, progress below thresholds, or response time above threshold. Counts overlap and must not be summed as unique projects.

All analytics and the registry share `search` (name/ID substring), exact `state`, exact `district`, `project_type`, `acquisition_stage`, and `indicator` filters. The indicator enum is `pending_approvals`, `legal_disputes`, `compensation_lag`, `possession_lag`, or `slow_response`; filtering and dashboard counts use the same SQL predicates. Analytics cover all matching records, regardless of table pagination. Each endpoint runs a database aggregation; the frontend does not derive totals from downloaded project pages. Separate endpoint requests are not a transactional snapshot during concurrent edits.

On empty results, counts are zero, averages are null, and distributions are empty arrays. The frontend displays skeletons during requests, an explicit empty state, and a retriable dashboard error instead of fake zero metrics.

Prototype threshold settings in `backend/.env.example`:

- `COMPENSATION_THRESHOLD_PCT=50`: strictly below 50%.
- `POSSESSION_THRESHOLD_PCT=50`: strictly below 50%.
- `SLOW_RESPONSE_DAYS=30`: strictly above 30 days.

Responses include the effective thresholds. These are configurable administrative indicators, not scientifically validated delay classifications. Progress averages are unweighted by land area or affected families. Land area uses hectares; timestamps serialize as explicit UTC.

## Testing and verification

```powershell
cd C:\LandGuard\backend
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd ..\frontend
npm run build
```

Unit tests use isolated SQLite databases and do not require PostgreSQL. They check CRUD, validation, duplicate handling, all shared filters, pagination, analytics, empty data, thresholds and boundaries, schema upgrades/downgrades, drift rejection, legacy record preservation, seed idempotency and PostgreSQL migration SQL generation.

Verified in this workspace: **48 tests passed, 1 PostgreSQL integration test skipped**, production build passed without bundle-size warnings, all five browser smoke suites passed, and Alembic reports head with no model/schema drift. Two third-party Starlette/httpx/AnyIO deprecation warnings remain in the test tooling; they do not affect the API or test outcomes.

For an actual PostgreSQL integration run, set a development connection string (not a production database):

```powershell
cd C:\LandGuard\backend
$env:TEST_POSTGRES_URL = "postgresql+psycopg://user:password@localhost:5432/landguard"
..\.venv\Scripts\python.exe -m app.db.verify_postgres
# Or:
..\.venv\Scripts\python.exe -m pytest tests/test_postgres.py -q
```

The integration check creates a uniquely named temporary schema, migrates it, seeds twice, exercises API CRUD and all dashboard endpoints, checks PostGIS coordinates after an update, and removes only its own schema. It may enable PostGIS in public if absent and leaves that shared extension installed. It needs schema-creation permissions. Without `TEST_POSTGRES_URL`, the integration test is explicitly skipped; the CLI can also use a PostgreSQL `DATABASE_URL`.

**PostgreSQL runtime verification could not be completed because the service was unavailable.** No PostgreSQL/Docker installation or configured PostgreSQL URL was found, and localhost:5432 did not accept a connection. PostgreSQL SQL generation checks are not runtime verification.

Browser checks are `frontend/browser-smoke.cjs` (CRUD) and `frontend/dashboard-smoke.cjs` (metrics against API responses, shared filters, loading, empty results, failure/retry, pagination and mobile layout). They require running servers, the illustrative seeds, Playwright available to Node and installed Microsoft Edge. For this Codex workspace:

```powershell
cd C:\LandGuard\frontend
$env:NODE_PATH = "C:\Users\ansum\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
node dashboard-smoke.cjs
node browser-smoke.cjs
```


## Interaction phase

The existing visual identity is preserved. KPI cards, bottleneck buttons, district bars and acquisition-stage bars now update a shared URL scope. Charts, metrics and table use the same backend filters; chips show the active selection. Search is debounced and obsolete requests are aborted. Pagination is URL-backed, and project detail/edit links retain a safe return URL so Back to results restores filters and the selected page.

Select a row or Quick view to open a project drawer (bottom sheet on mobile), with recorded progress, administrative counts and coordinates. The three-dot menu offers quick view, details, edit, geographic context and copy ID. Detail sections use keyboard-accessible tabs; secondary metadata expands on demand. GIS and ML remain explicitly unavailable. Record history contains only actual creation/update timestamps.

Ctrl/Cmd+K opens project, district and route search with arrow-key navigation, Enter and Escape. The header bell and sidebar Review notices open a prototype inbox. Its unread count covers the records shown; read state is stored in this browser and keyed to each record's update timestamp. No alert severity, prediction or event history is invented. Successful project mutations and notice read actions provide restrained toast feedback.

Refresh fetches current data without reloading the page and reports the successful fetch time. A shared abortable resource hook handles loading, errors, retry and mutation invalidation without adding another dependency. No offline cache or cross-tab/server read synchronization is claimed. Sidebar collapse persists locally. Motion is limited to brief state transitions, initial progress fill and KPI values, and honors reduced-motion preferences.

Additional checks: `node interaction-smoke.cjs` covers all five requested flows, active URL scope, tooltips, context menu, detail-tab keyboard handling, Ctrl+K, local notice read state, refresh and mobile sheets. `node ui-smoke.cjs` checks six viewport widths. Run alongside the dashboard and CRUD smoke suites with the same Playwright setup above.

## Recommended next phase

`node motion-smoke.cjs` additionally verifies rendered progress percentages, reduced-motion behavior, and restoration of pagination after viewing details.

First run the prepared PostgreSQL/PostGIS integration check once a service and development connection are available. Then establish the ML data contract and evaluation infrastructure: define project-observation timestamps and delayed-outcome labels, audit dataset provenance/leakage, and prepare preprocessing and candidate-model validation. Train only when an appropriate labeled dataset exists. No training command or model-performance claims exist yet. Authentication/RBAC remains necessary before shared deployment.

## System administrator role separation

LandGuard now separates technical account administration from land-acquisition operations.

- `SYSTEM_ADMIN`: manages users, invitations, account status, and account activity only. It cannot read project records, dashboards, GIS data, operational alerts, or AI intelligence.
- `STATE_OFFICER`: operational access to projects within the assigned state; state officers can delete projects within that state scope.
- `DISTRICT_OFFICER`: operational access to projects within the assigned state/district.
- `IMPLEMENTING_AGENCY`: operational access only to explicitly assigned project IDs.

If `backend/supabase/001_identity.sql` was already applied before this change, run `backend/supabase/002_system_admin_role.sql` once in the Supabase SQL Editor. This migrates the legacy `ADMIN` profile to `SYSTEM_ADMIN` and updates the role constraint/bootstrap function.

For a new Supabase project, use the updated `backend/supabase/001_identity.sql`; do not also run `002_system_admin_role.sql` unless you are upgrading an older installation.
