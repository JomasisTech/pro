# DEMO-ONLY image for Render, placed at the repository ROOT so Render's default settings work
# (Root Directory empty, Dockerfile path ./Dockerfile, build context .). Nothing else needs configuring.
# Never use this for production (use backend/Dockerfile). See docs/demo-mode.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEMO_MODE=true \
    APP_ENV=staging \
    DATABASE_URL=sqlite+pysqlite:///./demo.db \
    PLATFORM_ADMIN_EMAILS=admin@example.com

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
