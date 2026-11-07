# Demo mode (local exploration)

Demo mode lets you open the whole app without registering, verifying email, setting up social login, or installing PostgreSQL/Redis.

## Backend (from `backend/`)
1. Set `DEMO_MODE=true`, `APP_ENV=development`, and `DATABASE_URL=sqlite+pysqlite:///./demo.db` in your shell or `backend/.env`.
2. `pip install -e ".[dev]"`
3. `uvicorn app.main:app --reload`

On startup it creates a SQLite file (`backend/demo.db`), adds categories and billing prices, and creates the demo account:
- Customer demo email: `customer-demo@example.com`
- Administrator demo email: `platform-owner-demo@example.com` (use the separate `/admin/login` button; no password entry is needed)
- Password for the customer demo: `pass`
- Customer workspace: "Demo Business" on the Premium plan, with a confirmed business profile (no onboarding screens). The administrator demo has its own isolated workspace.

## Frontend (from `frontend/`)
1. Create `.env.local` containing `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`
2. `npm install` then `npm run dev`
3. Open http://localhost:3000/login and tap **Enter customer demo**.
4. Open http://localhost:3000/admin/login and tap **Enter administrator demo** to access `/platform` with a separate platform-owner identity.

## Limits
- PostgreSQL is NOT needed in demo mode. Alembic migrations are skipped; tables are created directly.
- Redis is not needed (rate limits stay in memory). Real email, Paystack, AI (OpenAI) and social platforms still need their own keys; without them those features show errors or stay disabled.
- Delete `backend/demo.db` to reset all demo data.
- The backend refuses to start if `DEMO_MODE=true` and `APP_ENV=production`.
- SQLite does not prove PostgreSQL compatibility; PostgreSQL verification is still outstanding (see `project-status.md`).

## Deploying the demo (Render backend + Vercel frontend)
**Render:** create a Docker web service from your repository with Dockerfile path `./backend/Dockerfile.demo` and Docker context `./backend` (or use `backend/render.demo.yaml` as the Blueprint file). That image is preconfigured for demo mode: SQLite database, no Alembic, a random secret key, any website allowed by CORS, demo account created at startup. **No environment variables are needed.** Health check path: `/health`.

**Vercel:** set ONE variable, `NEXT_PUBLIC_API_BASE_URL` = your Render URL (https, no trailing slash), then redeploy. The customer login page asks the API whether demo mode is on and shows the customer demo box automatically. The separate administrator login page uses `POST /api/v1/auth/demo-admin` and signs in as `DEMO_ADMIN_EMAIL`.

Notes: Render free services sleep when idle (first request can take about a minute) and the SQLite file resets on every restart; the demo account is recreated automatically. Anyone who finds the public demo URL can enter either demo experience, so use it only for testing and store no real data. The customer and administrator demo identities are separate; customer demo tokens do not receive platform-admin permissions. `Dockerfile.demo` must never be used for production.
