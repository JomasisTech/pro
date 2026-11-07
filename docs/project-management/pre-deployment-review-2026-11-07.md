# Pre-deployment review — 2026-11-07

## Scope reviewed

Reviewed the current project archive after the dashboard KPI-card refinement and the purple-glass authentication refresh. The review covered the Next.js authentication routes and shared styles, dashboard KPI layout, frontend environment configuration, backend production settings, Render service definitions, Dockerfiles, and the repository's recorded release blockers.

## Corrections made in this review

- Removed the authentication-page radial glow/orbit artwork. The login and registration pages now use a clean purple gradient canvas and translucent glass card without floating circles.
- Reused the same purple-glass shell for password recovery, password reset, email verification, and WhatsApp sign-in so the signed-out experience is visually consistent.
- Updated recovery feedback panels and primary actions for readable contrast on the dark purple surface.
- Hardened the post-login `next` redirect: it now accepts only same-origin path destinations and rejects protocol-relative/external destinations, including URL forms normalized through backslashes.
- Added a production build guard requiring `NEXT_PUBLIC_API_BASE_URL` to be an absolute HTTPS backend URL, preventing a deployed frontend from silently falling back to localhost.
- Added `/verify-email` to the public-route allowlist so a newly registered user sees the verification screen without the authenticated application navigation.
- Tightened backend production configuration to require PostgreSQL, HTTPS CORS/frontend/media origins, SMTP, and a non-placeholder sender address.
- Confirmed the dashboard KPI component uses a horizontal icon + text layout, two columns on mobile, compact card sizing, and a separate chevron. The four metrics are derived from the current API-backed dashboard data rather than hardcoded sample totals.

## Checks actually performed

- Python `compileall` over `backend/app`, `backend/tests`, and `backend/migrations`: passed.
- Direct production-settings checks: valid configuration accepted; SQLite, HTTP frontend/CORS, missing SMTP, and placeholder sender rejected.
- Login redirect test vectors: local paths accepted; external/protocol-relative and backslash-normalized external paths rejected.
- Auth source/visual regression checks: passed; no radial-gradient or pseudo-element orbit artwork remains in the shared auth styles.
- ZIP integrity check: to be performed on the final delivery archive.

## Checks blocked in this environment

- Backend pytest could not start because the local environment is missing the declared `pyotp` dependency (and `redis` is also absent). Installing project dependencies failed because this environment could not reach the package index.
- Frontend `npm install` timed out because this environment could not reach the package registry. The repository has no `package-lock.json`; therefore lint, TypeScript, Next.js production build, and browser/mobile visual QA were not run.
- No live PostgreSQL 16 database, Render environment, SMTP mailbox, Paystack account, or social-provider developer credentials were available. Database migration behavior, concurrency, OAuth, publishing, webhook delivery, email delivery, scheduled jobs, and live payments are not certified by this review.

## Deployment decision

**Not cleared for production deployment yet.** The source archive can be used for continued staging validation, but the application README and project status correctly record that the project is not production-ready. Do not treat a clean source inspection or SQLite tests from earlier increments as proof of PostgreSQL or live-provider readiness.

## Required release gates

1. Generate and commit a real `frontend/package-lock.json` with Node 22/npm 10 in a network-enabled environment; then run `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build`.
2. Run the complete backend suite and all Alembic migrations against PostgreSQL 16; include concurrency/integration checks that require PostgreSQL.
3. Deploy to staging using `backend/render.yaml` for the production API/cron topology and the `frontend/` directory as the Vercel project root. The root `Dockerfile` is explicitly demo-only and must not be used for production.
4. Configure Vercel `NEXT_PUBLIC_API_BASE_URL` to the HTTPS backend API origin before the frontend build; the production Next.js config now fails fast if it is missing or non-HTTPS. Configure Render `DATABASE_URL`, unique `SECRET_KEY`, `REDIS_URL`, exact `CORS_ORIGINS`, `FRONTEND_BASE_URL`, HTTPS `MEDIA_PUBLIC_BASE_URL`, and persistent media storage. Copy the same required secrets into the relevant cron services where needed.
5. Configure and verify SMTP before relying on password reset, verification, invitation, or billing email. Keep `EMAIL_VERIFICATION_REQUIRED=false` until delivery is tested; enable it only after successful inbox testing.
6. Verify health/readiness, registration, email verification, login/logout, password reset, workspace isolation, mobile layouts, and protected routes in a real browser on staging.
7. Verify each enabled OAuth/publishing provider with its real callback URLs, app permissions, test accounts, token encryption key, and provider review requirements. Keep unverified providers disabled.
8. Test Paystack in test mode end to end: checkout, webhook signature, server verification, idempotent fulfillment, return URL, and recovery. Keep `BILLING_RENEWALS_ENABLED=false` and `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` until the full renewal/SMTP operational checklist is completed and explicitly approved.
9. Confirm Render cron execution and monitoring for billing maintenance and YouTube processing. Keep a single API instance while local persistent media storage is used; do not scale horizontally until shared/object storage and worker coordination are addressed.
10. Confirm backups, restore procedure, error monitoring, log redaction, domain/HTTPS, and rollback procedure before public launch.

## Deployment configuration notes

- Frontend local environment template: `frontend/.env.example` (localhost default is for local development only).
- Backend production service and cron definitions: `backend/render.yaml`.
- Root `Dockerfile`: demo-only, as stated in the file itself; production API uses `backend/Dockerfile`.
- Billing scheduler and flags: `docs/operations/billing-scheduler.md`.
- Authentication setup and callback requirements: `docs/authentication-api.md` and `docs/google-sign-in.md`.
