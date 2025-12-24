#!/usr/bin/env bash
set -e

echo "[orders] Running migrations..."
alembic upgrade head

echo "[orders] Starting app..."
exec uvicorn orders.main:app --host 0.0.0.0 --port 8000 --app-dir src
