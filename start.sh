#!/usr/bin/env bash
# Starts Saarthi: FastAPI backend (:8000) + Vite frontend (:5173)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
[ -f .env ] || cp .env.example .env
PY=.venv/bin/python; [ -f "$PY" ] || PY=.venv/Scripts/python
"$PY" -m uvicorn app.main:app --port 8000 &
trap "kill $! 2>/dev/null" EXIT
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev
