#!/usr/bin/env bash
# Container entrypoint: wait for Postgres, run Alembic migrations, then start Uvicorn
set -euo pipefail

echo "[entrypoint] waiting for database at ${DATABASE_HOST:-postgres}:${DATABASE_PORT:-5432}..."
for i in $(seq 1 30); do
  if python -c "import psycopg2; psycopg2.connect(host='${DATABASE_HOST:-postgres}', port='${DATABASE_PORT:-5432}', user='${DATABASE_USER:-lh}', password='${DATABASE_PASSWORD:-lh}', dbname='${DATABASE_NAME:-learning_hub}').close()" 2>/dev/null; then
    echo "[entrypoint] database reachable"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[entrypoint] database not reachable after 30 attempts, exiting"
    exit 1
  fi
  sleep 1
done

echo "[entrypoint] running alembic upgrade head..."
alembic upgrade head 2>/dev/null || echo "[entrypoint] alembic skipped (no migrations yet)"

echo "[entrypoint] starting uvicorn on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
