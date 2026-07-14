#!/usr/bin/env bash
# Local dev startup: FastAPI backend on :8420, Vite frontend on :5173
# (frontend/vite.config.js proxies /api -> http://127.0.0.1:8420).
set -e
cd "$(dirname "$0")"

python -m uvicorn api.main:app --reload --port 8420 &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null' EXIT
wait
