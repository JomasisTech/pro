# Local PostgreSQL development

AutoBizPro uses PostgreSQL as its intended application database. SQLite is used only by lightweight isolated tests that do not need to validate PostgreSQL-specific behavior.

## Requirements

- Docker Desktop or Docker Engine with the Docker Compose plugin
- Python 3.12 or newer

## 1. Start PostgreSQL

Run these commands from the repository root:

```bash
docker compose up -d postgres
docker compose ps
```

Wait until the `postgres` service reports healthy.

The Compose configuration creates a local database with these development-only values:

- Database: `business_automation`
- User: `app_user`
- Password: `dev_only_change_me`
- Host/port: `127.0.0.1:5432`

The port is bound to localhost and the named volume preserves database data between container restarts. These credentials are for local development only. Never reuse them in staging or production.

## 2. Configure the backend

Copy `backend/.env.example` to `backend/.env`. The example's `DATABASE_URL` matches the local Compose service. If you change the local database credentials or port, update the URL too.

```bash
# macOS/Linux, from the repository root
cp backend/.env.example backend/.env
```

On Windows PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
```

Do not commit `backend/.env`. The repository's `.gitignore` excludes environment files.

## 3. Install backend dependencies and start the API

```bash
cd backend
python -m venv .venv
```

Activate the environment, then install the backend and development dependencies:

```bash
# macOS/Linux
source .venv/bin/activate
pip install -e ".[dev]"

# Windows PowerShell activation instead:
# .\.venv\Scripts\Activate.ps1
```

From the `backend/` directory, run:

```bash
uvicorn app.main:app --reload
```

Check `http://127.0.0.1:8000/health` for process health and `http://127.0.0.1:8000/ready` for database readiness. `/ready` should return HTTP 200 with `{"status":"ready","database":"ok"` when PostgreSQL is reachable.

## 4. Run automated tests

Run the current isolated tests from `backend/`:

```bash
pytest -q
```

These tests deliberately use an in-memory SQLite database for fast endpoint checks. They do not prove PostgreSQL connectivity.

To run the optional PostgreSQL connectivity test, set `TEST_POSTGRES_URL` to a test database URL and run the same test suite. The test executes only `SELECT 1`; it does not create, alter, or delete tables. For local Compose, the URL is:

```text
postgresql+psycopg://app_user:dev_only_change_me@localhost:5432/business_automation
```

Keep this variable unset when PostgreSQL is not available; the integration test will be skipped.

## 5. Stop PostgreSQL

```bash
docker compose down
```

This stops the container but preserves the named volume. To permanently delete the local database data, use `docker compose down -v` only when you intentionally want to reset it.

## Production rules

- Use a managed PostgreSQL instance or a securely managed database service.
- Configure `DATABASE_URL` through the hosting provider's secret/environment settings.
- Use unique strong credentials and TLS where supported.
- Apply schema changes through Alembic migrations, not manual production edits.
- Run PostgreSQL-backed integration tests before shipping database-dependent features.
