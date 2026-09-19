# LandGuard AI — Render Deployment

This deployment keeps the React SPA and FastAPI API on **one origin**. FastAPI serves the Vite production build, which keeps LandGuard's session cookie and CSRF/origin checks same-site.

## Architecture

- Render Web Service: React production build + FastAPI
- Supabase: Auth and PostgreSQL/PostGIS database
- Brevo: invitation email delivery
- PAIMANA automatic monitor: disabled for the SIH demo

## 1. Push the project to GitHub

Commit the deployment files at the repository root:

- `Dockerfile`
- `.dockerignore`
- `render.yaml`
- `deploy/start.sh`
- updated `backend/app/main.py`
- updated `backend/app/db/session.py`

Do **not** commit `.env`, Supabase service-role keys, Brevo keys, or database passwords.

## 2. Prepare Supabase

Use a Supabase PostgreSQL connection string as `DATABASE_URL`. A normal `postgresql://...` URL is accepted by the patched backend and is normalized to the project's psycopg v3 driver.

If PostGIS is not already available in the database, enable the PostGIS extension in Supabase before deployment. LandGuard's Alembic migration also attempts `CREATE EXTENSION IF NOT EXISTS postgis`.

Use a persistent PostgreSQL database for the deployed demo. Do not rely on the local SQLite default on Render because container files are ephemeral.

## 3. Create the Render service

In Render:

1. **New → Blueprint**
2. Connect the GitHub repository containing `render.yaml`.
3. Render will create one Docker web service named `landguard-ai-sih2026`.
4. Enter the secret environment variables requested by the Blueprint.

Required secrets:

```text
DATABASE_URL
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Required for invitation email delivery:

```text
BREVO_API_KEY
BREVO_SENDER_EMAIL
```

The Blueprint already sets:

```text
PUBLIC_APP_URL=https://landguard-ai-sih2026.onrender.com
FRONTEND_ORIGIN=https://landguard-ai-sih2026.onrender.com
SEED_DEMO_DATA=true
PAIMANA_AUTO_MONITOR_ENABLED=false
```

If you rename the Render service or attach a custom domain, update **both** `PUBLIC_APP_URL` and `FRONTEND_ORIGIN` to the exact HTTPS origin with no path and no trailing route.

## 4. What happens on startup

The container startup script performs:

```text
alembic upgrade head
      ↓
optional canonical SIH demo seed
      ↓
uvicorn FastAPI server
```

With `SEED_DEMO_DATA=true`, the eight `P-RGD-*` Rayagada demonstration records are refreshed. They remain explicitly `ILLUSTRATIVE` records.

Set `SEED_DEMO_DATA=false` when you no longer want demo records refreshed during deploys.

## 5. Frontend deployment behavior

The Docker build runs:

```text
npm ci
npm run build
```

and copies `frontend/dist` into the final Python image.

FastAPI then serves:

```text
/api/v1/*  → API
/assets/*  → Vite assets
/*         → React SPA fallback
```

`VITE_API_URL` is intentionally blank in production so the frontend calls the API on the same origin.

## 6. Health check

Render checks:

```text
/api/v1/health
```

A healthy response confirms database connectivity and reports whether the model artifact is available.

## 7. Demo safety

For the SIH demo keep:

```text
PAIMANA_AUTO_MONITOR_ENABLED=false
```

The admin pipeline can still be shown, but the deployment will not unexpectedly ingest or retrain while you are presenting.

## 8. Verify after deploy

Open the public Render URL and test in this order:

1. `/api/v1/health`
2. Login as District Officer
3. War Room / Risk Pulse
4. Project Quick View
5. GIS
6. Process Twin
7. AI Intelligence
8. SHAP + historical analogues
9. Intervention Simulator
10. Create/update/resolve an Intervention
11. Officer Brief
12. Login as System Admin and verify project APIs remain blocked

## 9. Common issues

### Login or write requests return 403

Verify these match the exact deployed HTTPS origin:

```text
PUBLIC_APP_URL
FRONTEND_ORIGIN
```

### Database driver error

Use a valid PostgreSQL URL. Generic `postgres://` and `postgresql://` schemes are normalized by the deployment patch to `postgresql+psycopg://`.

### PostGIS migration fails

Enable PostGIS in the Supabase database, then redeploy.

### Site opens but React routes 404

The deployment patch includes a SPA fallback. Confirm the Docker frontend build succeeded and `/app/frontend/dist/index.html` exists in the image.

### Model loading warning

The project pins `scikit-learn==1.9.1` to match the shipped model artifacts. Do not loosen that version for the demo image.

## Local Docker test (optional)

```powershell
docker build -t landguard-ai .
docker run --rm -p 10000:10000 `
  -e PUBLIC_APP_URL=http://127.0.0.1:10000 `
  -e FRONTEND_ORIGIN=http://127.0.0.1:10000 `
  -e DATABASE_URL="..." `
  -e SUPABASE_URL="..." `
  -e SUPABASE_SERVICE_ROLE_KEY="..." `
  -e PAIMANA_AUTO_MONITOR_ENABLED=false `
  landguard-ai
```

Then open `http://127.0.0.1:10000`.
