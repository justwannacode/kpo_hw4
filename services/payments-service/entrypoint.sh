#!/usr/bin/env bash
set -e

echo "[payments] Running migrations..."
alembic upgrade head

echo "[payments] Starting app..."
exec uvicorn payments.main:app --host 0.0.0.0 --port 8000 --app-dir src
