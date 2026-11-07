# Stage One remediation report — v0.2.5 working archive

Date: 2026-11-04
Baseline: `bizpilotpro_v0_2_4_phase1_completion.zip`

## Changes made

1. **Frontend CSS build foundation** — added `tailwindcss` v4 and `@tailwindcss/postcss` development dependencies and created `frontend/postcss.config.mjs` for the existing `@import "tailwindcss"` / `@theme` stylesheet.
2. **Render Docker context** — changed `dockerContext` from repository root to `./backend`, so `COPY pyproject.toml`, `COPY app`, `COPY migrations`, and `COPY alembic.ini` resolve from the actual backend directory.
3. **Production origins** — added Render environment settings for `CORS_ORIGINS` and `MEDIA_PUBLIC_BASE_URL`. Production configuration rejects localhost CORS entries, empty origins, and missing/non-HTTPS media API origins. Set the actual frontend origin(s) and public HTTPS API origin in Render before deploying.
4. **Scheduling authorization** — schedule creation now requires owner/admin role in addition to the existing central scheduled-post quota dependency. A schedule creation by an approver is the explicit approval-and-publish action. Ordinary members cannot directly insert unapproved content into the publishing queue.
5. **TikTok media pre-validation** — files smaller than 5 MiB are rejected during upload, instead of being accepted and failing later in the scheduled worker.
6. **Regression coverage** — added tests for non-approver schedule rejection, production CORS/media configuration, minimum upload size, and an optional PostgreSQL registration/scheduling workflow.
7. **Project records** — updated project status and known issues to record the fixes and remaining verification requirements.

## Verification

- Backend pytest: **178 passed, 2 skipped** using SQLite.
- SQLite Alembic upgrade: passed through `20261104_0020`.
- `alembic check`: no new upgrade operations detected.
- Python compileall: passed.
- PostgreSQL application integration: test added but skipped locally because `TEST_POSTGRES_URL` was not available.
- Frontend dependency install: `npm install` timed out in this environment. Frontend lint and production build were therefore not run. `package-lock.json` remains outstanding.
- Render Docker image build and live deployment: not run.

## Known remaining work

- Link scheduled posts to specific approved `ContentDraft` records with a required draft ID and immutable approved-content snapshot. The current fix makes scheduling an owner/admin-only approval action, but does not create this stronger traceable draft relationship.
- Obtain a real PostgreSQL CI run and validate the full application workflow there.
- Generate and commit a frontend lockfile in a network-enabled environment, then run lint and production build.
- Verify Render's actual image build and configure the required production environment values.
- Continue the remaining authentication, distributed rate limiting, social token lifecycle, scheduler idempotency, media lifecycle, activity-log coverage, and Hybrid Brand Intelligence work tracked in `known-issues.md`.
