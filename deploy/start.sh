#!/usr/bin/env bash
set -euo pipefail

cd /app/backend

echo "[deploy] Applying database migrations..."
alembic upgrade head

if [[ "${SEED_DEMO_DATA:-false}" == "true" ]]; then
  echo "[deploy] Refreshing canonical illustrative SIH demo data..."
  python -m app.db.seed
fi

echo "[deploy] Starting LandGuard on 0.0.0.0:${PORT:-10000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" --proxy-headers --forwarded-allow-ips='*'
