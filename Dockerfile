# Saarthi: one container serving the FastAPI backend and the built React frontend.
#   docker build -t saarthi .
#   docker run -p 8000:8000 -v saarthi-data:/data -e GEMINI_API_KEY=... saarthi

# ---- 1. Build the frontend
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python runtime
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SAARTHI_DATA_DIR=/data \
    SAARTHI_FRONTEND_DIST=/app/frontend/dist \
    DEMO_MODE=true \
    PORT=8000

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# The knowledge base is read from ../knowledge relative to backend/
COPY knowledge/ knowledge/
COPY backend/app/ backend/app/
COPY --from=web /web/dist/ frontend/dist/

RUN useradd --create-home --uid 1000 saarthi && mkdir -p /data && chown saarthi:saarthi /data
USER saarthi
VOLUME ["/data"]

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"
# Single worker: SQLite + in-process background agent runs. Scale with a bigger box, not more workers.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
