# Increment 31 — audit fixes (2026-11-05)

Static audit of the Increment 30 merge found deployment and frontend/backend parity gaps. Fixed here:

1. `render.yaml`: API service now declares `REDIS_URL` (production startup requires it) plus Paystack, encryption-key, Meta, TikTok, Google, WhatsApp and platform-admin variables.
2. `backend/Dockerfile`: runs `alembic upgrade head` before starting uvicorn. Cron services override the command and do not migrate.
3. New cron `python -m app.jobs.poll_youtube_processing` (every 5 minutes) and Render cron service `bizpilotpro-youtube-processing`; test `tests/test_poll_youtube_job.py`.
4. Added `backend/.env.example`, `frontend/.env.example`, and a Redis service in `compose.yaml`.
5. Workspace page: members list, owner-only role change and removal (uses existing endpoints). Also fixed the invitation Revoke button leaving the page stuck in a busy state.
6. Brand Intelligence page: "Analyze without AI" (`?method=rules`) and rendering of rule-based results (evidence level, writing patterns, suggestions).

## Verification
Python compile passed; TypeScript syntax check on edited files passed. NOT run: pytest (the new tests included), `npm install`/lint/typecheck/build, browser testing, a real Render deploy.

## Still open
Frontend lockfile; `frontend/public` assets; activity-log filter UI and logging of logins/registrations/AI generations; manual-observation UI; WhatsApp-only accounts cannot add email/password; TikTok/YouTube shared scheduling; refunds/disputes/invoices; supervised separate workers.
