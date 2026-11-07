# BizPilot Pro (AutoBizPro)

**Customer-facing product name:** AutoBizPro. BizPilot Pro is the internal project/repository name; the frontend brand, metadata and user-facing messages use AutoBizPro.

BizPilot Pro is a modular-monolith SaaS platform. Product 01 is Social Media Automation: business-aware AI content creation, content management, and (in later slices) social account connections, scheduling, publishing, and analytics.

## Current implementation snapshot — remediation archive v0.2.7

The repository contains a FastAPI backend, a Next.js frontend, organization-based authentication and authorization, business profiles, AI caption generation, saved drafts, usage limits, and an organization activity log. Hybrid Brand Intelligence supports queued and automatic latest-20 ingestion for Instagram, Facebook Pages, TikTok, and YouTube through official provider APIs; YouTube requires `youtube.readonly` and existing accounts must reconnect to grant it. The onboarding profile has been expanded with explicit niche and additional audience/brand-preference fields. Caption generation consumes a shared, tenant-scoped business context service.

The v0.2.7 remediation archive retains the v0.2.6 approved-draft scheduling controls and profile-confirmation activity logging, and adds Instagram long-lived token refresh before expiry plus conservative handling of ambiguous Facebook/Instagram publishing failures to reduce duplicate-post risk. See `docs/project-management/remediation-v0.2.7.md` for exact changes and verification.

The project is not production-ready yet. Billing now includes Paystack checkout, customer subscription management, optional recurring-consent and authorization storage, renewal-attempt tracking, customer OTP/3DS handoff, pre-charge notices, verification-only recovery, a narrow provider-directed regulator retry, and a managed billing-maintenance scheduler. **Automatic renewals and billing email notifications remain disabled by default.** Real SMTP inbox delivery, PostgreSQL 16 concurrency verification, live Paystack test-mode behavior, Render cron deployment/alerts, frontend dependency installation/lint/build, browser end-to-end testing, live social-provider verification, and deployment verification remain outstanding. Production configuration now fails fast if PostgreSQL, HTTPS frontend/API origins, Redis, SMTP, or a non-placeholder sender are missing. See `docs/project-management/project-status.md`, `docs/project-management/pre-deployment-review-2026-11-07.md`, and `docs/operations/billing-scheduler.md` for the authoritative release gates and operational runbook.

## Repository layout

- `backend/` — FastAPI, SQLAlchemy models, Alembic migrations, API routes, services, and tests.
- `frontend/` — Next.js application.
- `docs/` — product requirements, API contracts, design references, and project-management records.
- `compose.yaml` — local service configuration.

## Local setup

1. Use Python 3.12+ and Node.js 22 with npm 10 for the frontend.
2. Start PostgreSQL using Docker Compose if Docker is available: `docker compose up -d postgres`.
3. Copy `backend/.env.example` to `backend/.env` and set a strong local `SECRET_KEY` and `DATABASE_URL`.
4. From `backend/`, create a virtual environment and run `pip install -e ".[dev]"`.
5. Run migrations from `backend/`: `alembic upgrade head`.
6. Start the API from `backend/`: `uvicorn app.main:app --reload`.
7. The frontend dependency lockfile is still outstanding because npm registry DNS was unavailable during Increment 29. Once `frontend/package-lock.json` is committed, install from `frontend/` with `npm ci`, then run `npm run dev`. Until then, a local `npm install` may resolve newer compatible versions and is not a reproducible CI install.
8. From `frontend/`, run `npm run lint`, `npm run typecheck`, and `npm run build` before submitting frontend changes.
9. Run backend tests from `backend/`: `pytest -q`.

See `docs/postgresql-development.md` for PostgreSQL verification guidance. SQLite tests are useful for fast feedback but do not prove PostgreSQL compatibility.

## Important documentation

- `AGENTS.md` — instructions for AI coding assistants.
- `docs/project-management/master-development-prompt.md` — canonical project brief and implementation strategy.
- `docs/project-management/project-status.md` — current implementation and verification status.
- `docs/business-onboarding.md` — onboarding and shared business-context contract.
- `docs/products/product-01-social-media/brand-intelligence-requirements.md` — agreed Hybrid Brand Intelligence requirements.
- `docs/business-profile-api.md` — business profile and context API contract.

Never commit `.env` files, access tokens, API keys, or real customer data. Use official platform APIs and OAuth; never request social-media passwords or bypass platform restrictions.

## TikTok video publishing

The TikTok publishing foundation includes creator-setting validation, explicit upload consent, browser-to-TikTok chunked upload, and durable publish-status tracking. See [`docs/tiktok-content-posting.md`](docs/tiktok-content-posting.md) for provider setup and audit requirements. Public posting stays disabled until TikTok's Content Posting API audit is approved.


## Production scheduling update (v0.2.0)

See [production scheduling and media operations](docs/production-scheduling-and-media.md) for the
background worker, persistent media disk, TikTok consent enforcement, and retry/recovery behavior.

## YouTube processing-status worker

YouTube video processing can now be polled independently after the browser upload has been completed and the video ID verified. From `backend/`, run `python -m app.modules.posting.youtube_worker` periodically under a process supervisor or scheduler. The worker checks durable jobs in `uploaded` or `processing` state and persists the provider's latest state. It does not recover an interrupted browser transfer when no video ID has been confirmed, and it has not been live-tested against YouTube. Do not run it as a production service until PostgreSQL and provider verification are complete.
