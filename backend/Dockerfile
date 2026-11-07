FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir .

EXPOSE 8000
# Apply pending database migrations, then start the API. If a migration fails the container exits
# and the previous release keeps serving. Cron services override this with their own dockerCommand.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
