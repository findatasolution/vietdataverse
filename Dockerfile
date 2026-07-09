# Viet Dataverse — single container: FastAPI backend + static FE (served at /fe).
# DBs are external (Neon); this image is stateless. Env is injected at runtime
# (docker compose env_file) — no secrets are baked in.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# curl for the HEALTHCHECK. psycopg2-binary ships libpq, so no build toolchain needed.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first — cached unless be/requirements.txt changes.
COPY be/requirements.txt /app/be/requirements.txt
RUN pip install --no-cache-dir -r /app/be/requirements.txt

# App code + static FE. fe/data/*.json is baked at build time, so a fresh
# "Update static chart data" commit + redeploy is what refreshes the charts.
COPY be/ /app/be/
COPY fe/ /app/fe/

WORKDIR /app/be
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

# 1 worker keeps RAM within the shared box's tight budget (no swap headroom).
# Bump only if traffic needs it AND the mem budget allows.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
