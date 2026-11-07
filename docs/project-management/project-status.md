# Project Status

> Historical increment notes below are snapshots from the time each feature was implemented. When an older note conflicts with a newer increment or `HANDOVER.md`, the latest dated increment and current handover are authoritative.

**Project:** BizPilot Pro — Social Media Automation  
**Current stage:** Stage E — Social Media Automation and foundation hardening  
**Status:** Product 01 includes social account OAuth/publishing foundations, scheduling/calendar and media capabilities, Brand Intelligence manual sync for Instagram/Facebook/TikTok/YouTube, durable sync-job records/worker, and a frontend sync dashboard. Increments 8–12 added Paystack signature/verification, durable payment persistence, provider adapters, managed pricing, customer checkout, signed webhook receipt, server-side verification and initial subscription activation. Increment 13 adds a verified-platform-owner customer directory, account suspension/reactivation with session invalidation, platform audit records, and payment operations diagnostics. Increment 14 adds manual retry for failed/stale Paystack success webhooks and visible admin audit history. Increment 15 adds a bounded scheduled reconciliation service/CLI for old pending Paystack payments plus a platform-admin run action. Increment 16 adds owner-managed period-end cancellation/resume, tenant-scoped payment history, configurable renewal grace periods, and a scheduled subscription lifecycle processor. Increment 17 adds the Paystack recurring-charge adapter primitive only. Increment 18 adds optional explicit recurring consent and encrypted storage of Paystack authorizations only when Paystack verifies them as reusable. Increment 19 adds a unique subscription-period renewal-attempt ledger and an opt-in scheduled Paystack renewal CLI with server-side verification and one-charge-per-period protection. Increment 20 adds a platform-admin top-10 customer lifetime-spend leaderboard with NGN/USD-separated rankings and ascending/descending sorting, backed by successful payment records and a responsive dashboard table. Increment 21 adds customer billing visibility for saved reusable payment authorizations and an owner-only Paystack authorization-deactivation workflow, connected to the billing page. Increment 22 adds durable Paystack paused/OTP/3DS challenge URL handling for renewal attempts, a tenant-scoped customer authentication handoff and a server-side return verification flow on `/billing`. Increment 23 adds a durable billing-email outbox, one-time automatic-renewal activation notices, advance renewal reminders, action-required/decline emails, bounded SMTP retries, and a hard gate that prevents automatic charges until the activation notice is successfully delivered. Increment 24 adds a verification-only reconciliation job for stale/incomplete renewal attempts, recovering successful or declined provider outcomes without initiating a second charge. Increment 25 adds Paystack-directed delayed retry handling only for explicit card-regulator retry windows (one retry maximum, rejected reference retained for audit and a fresh unique reference used for the retry), a unified five-minute billing-maintenance runner, a Render cron service, structured operational summaries, and a controlled SMTP readiness command. The renewal worker remains disabled by default; live Paystack test-mode validation, PostgreSQL concurrency and scheduler operations remain before activation. Refunds/disputes remain unimplemented. PayPal and Flutterwave remain future providers; Google Pay is a Paystack Checkout channel. Focused tests described in each increment use SQLite and/or mocked provider responses; PostgreSQL 16, frontend install/lint/build/browser QA, live provider behavior, multi-replica worker supervision, and production deployment remain unverified. The focused Increment 19 billing regression set passed 54 tests; Increment 20 platform-admin tests passed 8 tests, including leaderboard ranking and access-control cases; Increment 21 focused billing/Paystack tests passed 24 tests, including owner authorization revocation and failure-safe retention. Increment 22 focused billing/platform tests passed 39 tests, including paused challenge URL validation and server-side return verification. Increment 26 executed all 51 backend test files in two bounded partitions: 361 passed and 3 PostgreSQL-gated tests skipped. The combined one-process run exceeded the execution window, but both partitions completed. Frontend dependencies remain absent, so frontend lint/build/TypeScript/browser checks are unverified.  
**Handover:** See [`HANDOVER.md`](HANDOVER.md) for the complete implemented/remaining checklist and instructions for the next AI/developer.  
## Increment 31 — owner profile controls, AI voice modes and admin recovery (2026-11-07)

Added `brand_voice_mode` (`automatic`, `manual`, `hybrid`) and `custom_ai_instructions` to the existing workspace business profile, with migration `20261107_0042`. Caption and video-script generation now consume only the latest owner/admin-approved Brand Intelligence proposal in automatic/hybrid modes; manual mode ignores social-derived voice. Owner-confirmed business facts remain authoritative. The `/profile` page now links to existing business, Brand Intelligence, social-account, workspace, security and billing areas and displays voice settings. Added platform-admin password recovery for active non-admin customers with an existing verified email; the admin supplies an audited support reason and the customer receives the standard one-time reset link to choose their own password. No admin password access, impersonation or unverified email bypass. Focused SQLite tests: 43 passed using a temporary external pyotp import stub because pyotp/psycopg are absent in the authoring environment. Fresh SQLite migration upgrade and `alembic check` passed. Full backend suite, PostgreSQL 16, frontend lint/typecheck/Vitest/build/browser QA, and real SMTP delivery remain unverified. See `increment-31-owner-profile-ai-voice-and-account-recovery-2026-11-07.md`.

## Increment 30 — invitation resend and rule-based brand analysis (2026-11-05)

Ported the few features missing from a parallel build: invitation resend with cooldown (migration `20261105_0040`), invitation status in the admin list, admin guard on revoking admin invitations, email verification on invitation acceptance, a no-AI rule-based brand analysis mode (`?method=rules`), and the first frontend Vitest suite. New API tests and the migration have **not been executed** in the authoring environment. See [`increment-30-merge-of-missing-features-2026-11-05.md`](increment-30-merge-of-missing-features-2026-11-05.md).

## Latest verification update — Increment 26 (2026-11-05)

Increment 26 inspected the Increment 25 repository and reconciled the current verification record without changing product code or database schema. The full backend test inventory (51 test files) passed in two bounded partitions: **361 passed, 3 skipped**. Python compilation passed. A file-backed SQLite migration run upgraded through `20261104_0039`, downgraded to `20261104_0038`, re-upgraded to head, and `alembic check` reported no new operations. The three skipped tests require PostgreSQL; PostgreSQL 16 was not available locally. Frontend lint/build could not run because `frontend/node_modules` and `package-lock.json` are absent and npm registry access was unavailable. Exact commands and limitations are in [`increment-26-stabilisation-audit-2026-11-05.md`](increment-26-stabilisation-audit-2026-11-05.md). Product 01 is still not live-verified or production-ready; automatic billing renewal and notification flags remain disabled.

## Latest verification update — Increment 27 (2026-11-05)

Increment 27 strengthens the frontend CI gate by adding an explicit `npm run typecheck` (`tsc --noEmit`) script and a dedicated TypeScript step to `.github/workflows/ci.yml`. Static inspection also found and fixed two frontend `Promise.all` result-destructuring defects: billing failed to capture its renewal-actions response, and platform administration failed to capture its top-customer response. README setup instructions now list lint/type-check/build and warn that `npm ci` requires a committed lockfile. The frontend lockfile could not be generated: npm's cache is empty and registry access failed with `EAI_AGAIN registry.npmjs.org`. Consequently, frontend installation, ESLint, a valid project TypeScript check, Next.js build, and browser/mobile QA remain unverified. A global `tsc` attempt was blocked by missing Next/React/Node declarations; after the two fixes it reported no remaining undefined-name (`TS2304`) diagnostics, but this does not substitute for the installed-project type check. The workflow was edited but not executed; no CI run result is claimed. See [`increment-27-frontend-ci-gate-2026-11-05.md`](increment-27-frontend-ci-gate-2026-11-05.md).

## Increment 28 — Future product requirements captured (2026-11-05)

The owner approved documenting a future AI-assisted lead-generation and outreach experience. Requirements are now recorded in:
- `docs/products/product-02-lead-management/requirements.md` — target understanding, business discovery, contact extraction/enrichment, normalization, email quality checks, explainable scoring, review, and lead-to-outreach handoff.
- `docs/products/product-06-data-collection/requirements.md` — approved source strategy, source adapters, provenance, rate limits, and collection compliance.
- `docs/products/product-04-email-marketing/requirements.md` — AI outreach drafting/review, customer approval, recipient eligibility, suppression/unsubscribe, delivery, and analytics.
- `docs/architecture/background-job-progress.md` — durable backend job/stage state and real-time frontend progress, with replayable SSE preferred and polling fallback.

The frontend requirement is explicit: customers should see backend-confirmed pipeline stages, current activity, useful counters, partial results, waiting/approval states, and clear errors. Progress must survive navigation/reconnects and must not be simulated. The existing Brand Intelligence sync-job implementation should be inspected and reused/generalized where appropriate.

**Scope clarification:** These are documented future requirements, not implemented features and not permission to start Products 02, 04, or 06 yet. Foundation hardening and Product 01 remain the active development scope.

**Last updated:** 2026-11-07 (Increment 31 — owner-controlled AI brand voice modes, approved social-insight integration, unified profile entry points, and audited admin password recovery; frontend validation and PostgreSQL remain outstanding)

## Latest verification update — Increment 29 (2026-11-05)

Increment 29 added explicit safeguards around destructive PostgreSQL integration tests. The two tests that recreate all application tables now require a deliberate opt-in, a local test host, and a disposable database name; only the isolated PostgreSQL 16 CI job opts in. Three guard tests were added. All 51 backend test files passed in two bounded groups (**364 passed, 3 skipped**), Python compilation passed, and SQLite Alembic upgrade/downgrade/re-upgrade plus `alembic check` passed with no schema drift. The three skipped tests require PostgreSQL. The PostgreSQL 16 workflow was inspected but not run from this environment; real PostgreSQL behavior remains unverified until a successful CI run is observed.

Increment 29 also attempted to generate `frontend/package-lock.json` with Node 22.16.0/npm 10.9.2. npm registry DNS resolution failed (`EAI_AGAIN registry.npmjs.org`) and bounded attempts timed out. No synthetic lockfile was created. Frontend install, lint, typecheck, production build, and browser/mobile QA remain unverified. Once a genuine lockfile is generated and reviewed, switch CI to `npm ci`.

See [`increment-29-postgres-and-frontend-lockfile-2026-11-05.md`](increment-29-postgres-and-frontend-lockfile-2026-11-05.md). Product 01 remains the active product; automatic billing renewal and notification flags remain disabled.



## Paystack webhook signature verification foundation — 2026-11-04 (Increment 8)

- [x] Added `backend/app/integrations/payments/paystack.py` with verification for modern timestamped `Paystack-Signature` headers using `PAYSTACK_WEBHOOK_SECRET`; the signed payload uses the exact raw body bytes and a five-minute timestamp tolerance.
- [x] Supports multiple `v1` signatures during Paystack webhook-secret rotation.
- [x] Retains legacy `x-paystack-signature` verification using `PAYSTACK_SECRET_KEY` while legacy events are still in use.
- [x] Uses constant-time signature comparison and rejects malformed/stale/tampered requests.
- [x] Added focused tests for modern, rotation, stale timestamp, legacy, malformed, wrong-secret, and tampered-body cases.
- [x] Verification: `tests/test_paystack_signatures.py`, `tests/test_billing_readiness.py`, `tests/test_plans.py` — **18 passed** on SQLite test environment; `python -m compileall -q app tests` passed.
- [ ] No webhook route, transaction persistence, checkout initialization, transaction verification, subscription lifecycle, or plan activation has been implemented. Checkout/webhooks remain disabled. Owner-approved prices are required before activation.
- [ ] Live Paystack test-mode webhook/signature rotation and transaction tests remain outstanding. See [`../paystack-billing.md`](../paystack-billing.md).

## Brand Intelligence synchronization dashboard — 2026-11-04

- [x] Connected the existing durable sync-job API to the Next.js Brand Intelligence page; manual sync buttons now enqueue work rather than synchronously waiting for provider API calls.
- [x] Added organization-scoped recent job history with queued/running/succeeded/failed states, attempt counts, timestamps, result counts, and safe error messages.
- [x] Added five-second polling only while one or more jobs are active; polling stops when all visible jobs reach a terminal state or the page unmounts.
- [x] Added retry action for failed jobs by enqueueing a new job through the existing deduplicating endpoint.
- [x] Updated the Brand Intelligence API contract documentation.
- [ ] Frontend dependency installation, TypeScript/ESLint/Next production build, and browser/mobile QA remain unverified because `frontend/node_modules` is not present in this environment.
- [ ] Verification in this increment: Brand Intelligence API, sync worker, and Instagram/Facebook/TikTok/YouTube media adapter tests — **25 passed** using SQLite and mocked provider responses; Python compilation passed. Live PostgreSQL, multi-worker contention, worker supervision, and real provider sync remain unverified.

## YouTube Brand Intelligence synchronization — 2026-11-04

- [x] Added an official YouTube Data API adapter that discovers the authenticated channel's uploads playlist and retrieves up to 20 recent uploads.
- [x] Normalizes video ID, title, description, publication timestamp, and canonical watch URL into the shared observation contract.
- [x] Expanded Google OAuth authorization to request `youtube.readonly` alongside `youtube.upload`; callback scope persistence retains the granted scopes.
- [x] Connected YouTube to the tenant-scoped, owner/admin-only Brand Intelligence sync endpoint, reusing encrypted credentials and the existing server-side Google token refresh helper.
- [x] Enforced the `youtube.readonly` grant and provided a reconnect message for existing accounts without it.
- [x] Enabled YouTube sync controls and video-specific result wording in the Brand Intelligence dashboard.
- [x] Added adapter, missing-scope, sync/upsert, and OAuth-scope regression tests.
- [x] Verification: YouTube media sync, OAuth, publishing, and processing-worker tests — **19 passed** using SQLite and mocked Google responses; Python compilation passed.
- [ ] Existing YouTube accounts must reconnect to grant `youtube.readonly`. Live Google/YouTube API behavior, Google OAuth verification, PostgreSQL, automatic background sync, and frontend build/browser testing remain unverified.

## TikTok Brand Intelligence synchronization — 2026-11-04

- [x] Added an official TikTok `video.list` adapter using `POST /v2/video/list/`, requesting only the metadata fields needed for evidence-backed analysis and limiting retrieval to 20 videos.
- [x] Normalizes video ID, description/title, share/embed permalink, creation timestamp, and video media type into the shared observation contract.
- [x] Extended the existing TikTok OAuth scope request to include `video.list`; existing `video.publish` permission is retained.
- [x] Connected TikTok retrieval to the existing owner/admin-only, tenant-scoped Brand Intelligence sync endpoint. Sync fails with a reconnect/permission message if the account has not granted `video.list`.
- [x] Uses the existing encrypted credential store, shared upsert/provenance/activity logging, and duplicate prevention.
- [x] Added server-side TikTok access-token refresh/rotation for Brand Intelligence sync when the token is within five minutes of expiry.
- [x] Updated the Brand Intelligence dashboard so TikTok accounts can initiate sync and the UI describes post/video retrieval.
- [x] Focused backend verification: TikTok adapter and token refresh, TikTok sync/upsert + missing-scope behavior, Brand Intelligence, social OAuth, TikTok publishing, Facebook media, and Instagram sync — **29 passed** using SQLite and mocked TikTok responses.
- [ ] Existing TikTok connections must be reauthorized to grant `video.list`; app approval/configuration for that scope is an external prerequisite. Live TikTok API behavior, refresh-token behavior, PostgreSQL, scheduled background synchronization, and frontend production build remain unverified.

## Facebook Page Brand Intelligence synchronization — 2026-11-04

- [x] Connected the existing Facebook Page OAuth credential store to the tenant-scoped Brand Intelligence sync endpoint.
- [x] Added an official Graph API Page-post adapter for up to 20 recent posts, normalizing post ID, message, permalink, and timestamp while keeping provider error details/tokens out of client responses.
- [x] Requires the existing `pages_show_list` and `pages_read_engagement` grants; Facebook Page credentials remain separate from Instagram token refresh.
- [x] Shared upsert/provenance/activity logging now records the actual provider for Instagram and Facebook.
- [x] Focused regression verification: Facebook adapter, Brand Intelligence sync, Facebook publishing and social OAuth tests — **19 passed** using SQLite and mocked provider calls.
- [ ] Live Meta Graph API permission/app-review validation, PostgreSQL verification, scheduled background sync/retries, and frontend production build remain outstanding. TikTok and YouTube read adapters are now implemented in later increments.

## Instagram Brand Intelligence synchronization vertical slice — 2026-11-04

- [x] Added an official Instagram Login media adapter that fetches at most 20 recent posts and normalizes available caption, media type, permalink, and timestamp fields.
- [x] Added owner/admin-only `POST /organizations/{organization_id}/brand-intelligence/sync/{social_account_id}`. It verifies tenant ownership, connected status, Instagram provider identity, and the `instagram_business_basic` scope before using the encrypted credential.
- [x] Reuses the existing Instagram long-lived-token refresh helper before retrieval; expired/unrefreshable credentials return a safe reconnect error.
- [x] Upserts by social account + provider post ID, records provider provenance, updates `last_synced_at`, and writes an activity-log event transactionally.
- [x] Added `/brand-intelligence` frontend page with connected-account sync controls, observed-post list, AI analysis trigger, and approve/reject proposal review. Added application navigation and updated the social-account page description.
- [x] Focused verification: `tests/test_instagram_media_sync.py` and `tests/test_brand_intelligence.py` — **4 passed**.
- [ ] Full backend suite remains unverified: first full run exposed a pre-existing email-outbox test expectation mismatch in `test_auth_sessions.py` (registration now emits a verification email); a subsequent run excluding that file exceeded the execution timeout after 74% progress.
- [ ] Frontend lint/build is unverified because frontend dependencies are not installed in this environment.
- [ ] Live Instagram API, Meta app review/permissions, PostgreSQL, and durable background synchronization remain outstanding. Facebook, TikTok, and YouTube adapters were added in subsequent increments.

## Production rate-limit configuration hardening — 2026-11-04

- [x] Production configuration now refuses to start with the in-memory rate-limit fallback: `REDIS_URL` must be present and use `redis://` or `rediss://`.
- [x] `/ready` now checks Redis connectivity whenever Redis is configured and returns a generic 503 if the shared rate-limit store is unavailable; Redis credentials and provider errors are not exposed.
- [x] Added regression tests for missing/invalid production Redis configuration and Redis readiness success/failure.
- [x] Verification: `python -m compileall -q backend/app backend/tests` passed; with `DATABASE_URL=sqlite+pysqlite:///:memory:`, focused config/rate-limit tests passed (**17 passed**).
- [ ] The readiness regression tests added in this increment have not yet been executed as part of the focused test run. Re-run `tests/test_health.py` and the full backend suite in an environment with the declared PostgreSQL driver installed.
- [ ] A real Redis ping, Redis concurrency/expiry behavior, PostgreSQL migration validation, live provider workflows, and frontend build/browser checks remain unverified.

## Latest audit implementation increment — 2026-11-04

- [x] Hardened the local failed-attempt limiter so its tracking dictionary remains capped when a high number of distinct, still-active keys arrive; at capacity it never evicts blocked keys, evicts unblocked keys fewest-failures-first in batches, and when all tracked keys are blocked applies a shared overflow budget to new keys, after first pruning expired entries.
- [x] Added a regression test for bounded key tracking.
- [ ] Redis-backed distributed rate limiting remains outstanding; the local limiter still resets on process restart and is not shared between workers.
- [ ] Frontend dependency installation/lockfile generation was attempted but timed out in this environment; no lockfile was generated and frontend build remains unverified.
- [ ] Backend pytest could not be started in this execution environment because the `psycopg` package is missing; this is an environment limitation, not a passing test result.

## Implemented in the current repository

- [x] FastAPI application, environment-based configuration, SQLAlchemy database setup, Alembic migrations, `/health`, `/ready`, and API root.
- [x] User, organization, and membership models; registration, login, current-user API; Argon2id password hashing with legacy PBKDF2 verification/upgrade.
- [x] Login rate limiting, proxy-aware client address handling, production secret guard, organization membership/role dependencies, and tenant-scoped organization APIs.
- [x] Workspace member role management (owner-only admin/member changes and member removal), plus expiring single-use email invitations and authenticated invitation acceptance (migration `20261104_0025`).
- [x] Dashboard authentication gate and workspace listing/creation/switching integration.
- [x] Industry categories and one-per-organization business profile; `/onboarding` form and onboarding redirect.
- [x] Expanded onboarding fields for explicit niche, audience type, geographic market, unique selling points, preferred tone/phrases, and avoided phrases.
- [x] Tenant-scoped business-context endpoint with core-profile completeness and user-provided provenance.
- [x] AI caption prompt incorporates the additional niche and brand preference fields when supplied.
- [x] Structured organization-owned products/services CRUD with tenant isolation and primary-product handling.
- [x] Business profile confirmation, onboarding completion timestamp, profile version number, and immutable profile change/confirmation snapshots.
- [x] Shared AI context includes active structured products/services and treats them as satisfying offer completeness.
- [x] AI caption generation using the business profile and an AI-provider abstraction.
- [x] AI Video Script Generator for TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, and long-form YouTube, with platform-aware structure, hooks, scene timings, voiceover, on-screen text, captions, descriptions, hashtags, and recording notes.
- [x] Separate monthly quota and hourly abuse guard for video-script generation; scripts can be edited and saved as drafts.
- [x] YouTube Google OAuth connection foundation with hashed one-time state, offline access, narrow `youtube.upload` scope, encrypted credentials, and provider readiness checks.
- [x] YouTube resumable upload initialization, 8 MiB browser chunk transfer with retry/probe handling, encrypted upload-session persistence, channel-scoped upload verification, processing-status API, and an independent database-backed processing poller (`python -m app.modules.posting.youtube_worker`).
- [x] `/youtube-publish` page for channel selection, video metadata, privacy, made-for-kids declaration, consent, upload progress, and processing status.
- [x] Central plan catalog, monthly usage tracking, quota enforcement, and usage endpoint.
- [x] Saved content drafts with edit/delete/approval actions and `/content` page.
- [x] Append-only organization activity log and `/activity` page; profile confirmation now records `profile.confirmed` transactionally alongside profile versions. Draft, profile, workspace, structured product/service, social-account connection/disconnection, and publishing lifecycle changes are logged transactionally.
- [x] GitHub Actions workflow for backend tests + PostgreSQL migrations and frontend lint/build.
- [x] Tailwind CSS v4 dependency and PostCSS plugin configuration.
- [x] Render Docker build context aligned with the backend Dockerfile.
- [x] Production CORS origins and public media API URL exposed as explicit Render environment settings and validated at startup.
- [x] Scheduling requires an existing approved organization-owned content draft; scheduled content must exactly match the approved draft, and linked drafts cannot be edited, re-approved/rejected, or deleted while linked to a scheduled/published record.
- [x] TikTok video uploads below the configured 5 MiB chunk minimum rejected during upload rather than later in the publishing worker.
- [x] Project blueprint, design references, API documentation, project-management records, and coding-agent instructions.

## Verification completed in earlier milestones

- [x] Fixed `NameError: sessionmaker is not defined` during collection of `tests/test_content.py` by importing `sessionmaker` from `sqlalchemy.orm`.
- [x] Earlier baseline backend test run: **109 passed, 1 skipped**.
- [x] `python -m compileall -q app tests`: passed.
- [ ] PostgreSQL application workflow test and migration verification: added a PostgreSQL-backed registration/scheduling test, but it was skipped locally because `TEST_POSTGRES_URL` is unavailable. SQLite migration upgrade reached `20261104_0020`; this does not establish PostgreSQL compatibility.
- [ ] Frontend dependency installation, lint, and production build: not completed; `npm install` timed out in this environment. Tailwind/PostCSS configuration is now present, but Next.js compilation remains unverified. `package-lock.json` is still absent.
- [ ] Browser-based end-to-end verification: not run.
- [ ] GitHub Actions CI: workflow is present but no run result is available in this project archive.
- [ ] Deployment configuration and live deployment: not verified.

## Known product gaps (current audit)

- Authentication: logout (token revocation), sign-out-everywhere, change password, and forgot/reset password are implemented in code (2026-11-04, migration `20261104_0020`) but not yet test-run. Email verification is implemented in code with single-use hashed tokens and optional enforcement (migration `20261104_0026`); SMTP delivery and full frontend workflow still require live verification. Refresh tokens and reviewed Secure/HttpOnly cookie sessions are not implemented.
- Login and AI generation rate limits are in-memory and unsuitable for multi-worker production; Redis-backed limits remain future hardening.
- Instagram, TikTok, YouTube and Facebook OAuth/publishing code exists, but none of the provider flows has been live-verified with production-like developer applications and customer accounts. Facebook supports Page text/link publishing and Meta-native scheduled posts only; personal profiles, Groups, photo/video/Reels are unsupported.
- TikTok Direct Post and YouTube resumable upload workflows exist in code, but require live-provider verification. TikTok failed uploads require a new session. YouTube now has independent background processing polling for uploads whose browser transfer was completed and verified; interrupted browser transfers still require a resumable-session recovery workflow.
- The calendar UI provides month, week, and 30-day agenda views. The organization-scoped feed aggregates saved drafts, Facebook entries, TikTok/YouTube publishing history, and shared scheduled-post records. The shared dispatcher currently supports Facebook text/link posts and Instagram single-image photo posts; TikTok/YouTube jobs remain upload-history entries, not scheduled posts.
- Hybrid Brand Intelligence has tenant-scoped observations/proposals, structured AI analysis, source provenance, conflict storage, owner/admin review, and a frontend review dashboard. Instagram, Facebook Pages, TikTok, and YouTube can manually trigger official API syncs of up to 20 recent posts/videos with provider-specific credentials and idempotent upserts. Durable background sync/retries, live provider verification, PostgreSQL verification, and automated frontend checks remain outstanding.
- AI caption/video-script generation has not been verified against a live OpenAI API call; tests use mocked providers.
- Billing/payment flows and plan upgrades are not implemented; plan values are placeholders.
- Frontend source exists for the implemented pages, but dependency installation timed out in this audit environment. Frontend lint, production build, and browser workflows remain unverified. Dashboard overview metrics are derived from fetched drafts, connected accounts, and workspace membership counts; the draft count is limited to the records returned by the drafts API.
- PostgreSQL 16, GitHub Actions execution, production deployment, and live third-party API behavior remain unverified. SQLite tests do not prove PostgreSQL compatibility.
- Workspace rename/delete, owner-only member role changes/removal, and invitation API + acceptance UI are implemented. Member-management/invitation administration UI (issuing and revoking invitations, viewing pending invitations) is still outstanding.

## Next tasks — stabilization before feature expansion

1. Continue repairing existing Product 01 behavior and close backend audit gaps, with regression tests for every fix.
2. Resolve deterministic frontend dependency installation/lockfile, then run lint and production build; fix all errors before browser QA.
3. Complete browser end-to-end verification for registration/login, workspace switching, onboarding/profile confirmation, products/services, drafts, social connections, publishing pages, and calendar.
4. Verify all migrations and backend tests against PostgreSQL 16 in CI or a real local PostgreSQL service.
5. Live-test each provider workflow with approved test apps/accounts and exact granted scopes; do not infer success from mocked tests.
6. Complete the existing scheduling/calendar and publishing-history requirements before implementing Brand Intelligence.
7. Implement Brand Intelligence only after the current social connection/publishing flows are stable and live-verified.
8. Harden authentication/session handling, replace in-memory rate limiting, and complete production security/operations review before commercial launch.

## Scope guard

The active scope remains the shared foundation and Product 01 — Social Media Automation. Products 02–07 in `docs/full-project-blueprint.md` are future roadmap items and must not be started yet.


## Social integration foundation (2026-11-02)
- Implemented social provider registry and organization-scoped social account inventory/disconnect APIs.
- Implemented Social Accounts frontend page and dashboard link.
- Added social account metadata migration 0008 and tenant/role tests.
- Backend tests: 111 passed, 1 skipped; SQLite migration through head and Alembic check pass.
- OAuth provider flows, secure token lifecycle, social post ingestion, analysis and profile review are not yet implemented. Frontend build/browser validation is still pending.

## Latest status — 2026-11-02 (supersedes earlier social-integration notes)

- Migration `20261102_0009` adds one-time OAuth state and encrypted social credentials.
- Instagram Login for professional accounts is implemented end-to-end in code: tenant/admin authorization start, hashed one-time state, server-side authorization-code exchange, long-lived-token exchange, account identity lookup, encrypted credential persistence, and callback result redirect.
- Instagram Connect and Facebook Page Connect are separate OAuth integrations, each enabled only when its own callback configuration and token-encryption key are present. A Facebook Page is never inferred from Instagram Login.
- Disconnect explicitly removes the encrypted credential as well as account metadata.
- Backend verification: **113 passed, 1 skipped**; compileall passed; SQLite migration upgrade through `20261102_0009` passed; `alembic check` reports no pending operations.
- Frontend changes are implemented in source, but npm install timed out again. Frontend lint/build/browser QA remain unverified.
- No real Meta credentials or public callback URL are configured; live OAuth and Meta app review/permissions are therefore unverified. PostgreSQL, GitHub CI, GitHub push and deployment are also unverified.

### Immediate next work

1. Configure a Meta developer app, HTTPS callback URL, app review/test-user access, and secrets outside source control; then perform a live Instagram professional-account authorization test.
2. Live-test the separate Facebook Login for Business/Page authorization flow, Page discovery and Page-token handling with a configured Meta developer app.
3. Add token refresh/revocation/deauthorization handling, scheduled account sync and latest-20 accessible post ingestion.
4. Implement analysis with onboarding details remaining authoritative, then user review/confirmation of the combined brand profile.
5. Resolve frontend package installation and run lint/build/browser QA; validate all migrations on PostgreSQL before production deployment.


### Latest social integration progress
TikTok Login Kit OAuth and Direct Post, Google OAuth and YouTube resumable upload, and Facebook Page OAuth/text-link publishing are implemented in code. None has been live-tested against configured provider apps/accounts. YouTube currently stores the authorized Google identity; explicit channel selection/verification and browser-closure recovery remain outstanding.


### TikTok OAuth verification details
- Automated tests cover OAuth start, state replay rejection, mocked token exchange, identity lookup, and encrypted access/refresh token persistence.
- Live TikTok authorization remains unverified until developer credentials and a public HTTPS redirect URI are configured.
- TikTok token refresh/rotation, creator-info validation, Direct Post upload, and status polling are implemented in code; live provider verification and upload-session recovery remain future work.

### TikTok Content Posting API

Implemented the initial Direct Post flow: creator settings, privacy and interaction controls, explicit consent, browser-to-TikTok chunk upload, durable publish tracking, and status refresh. Unreviewed apps are hard-limited to `SELF_ONLY` by default. Live TikTok testing, provider audit, upload-session retry/resume, and frontend build validation remain outstanding. TikTok access-token refresh/rotation is now handled when an API request detects a near-expiry token.


### YouTube OAuth foundation

Google OAuth connection is implemented using a hashed one-time state, server-side authorization-code exchange, OpenID account identity, offline access, `youtube.upload` plus `youtube.readonly` scopes, and encrypted access/refresh-token storage. The social-account UI enables YouTube Connect only when Google OAuth credentials and the encryption key are configured. This connects the Google identity associated with YouTube authorization; explicit channel selection/identity verification and browser-closure upload recovery remain outstanding. Resumable `videos.insert` upload and processing-status checks are implemented in code.


### YouTube resumable publishing — 2026-11-02

- Added migration `20261102_0011` and organization-scoped `youtube_publish_jobs` records. Resumable session URLs are encrypted at rest.
- Added owner/admin YouTube upload initialization using the official `videos.insert` resumable protocol, 8 MiB browser chunks, transient retry/status probes, upload-ID verification, and processing-status lookup.
- Added `/youtube-publish` with channel selection, file upload, title/description/tags, privacy, made-for-kids declaration, explicit consent, progress and status. Added navigation from Social Accounts.
- YouTube is marked complete only when provider processing confirms success; Shorts classification is left to YouTube.
- Verification: **124 passed, 1 skipped**; Python compileall passed; SQLite Alembic upgrade through `20261102_0011` passed; `alembic check` reports no pending model changes.
- Not yet verified: frontend build/browser CORS behavior, PostgreSQL migration, Google OAuth verification, real channel upload, quota, and public deployment. Recovery after browser closure and background status polling remain incomplete.

### Facebook Pages / calendar
Facebook Pages OAuth and text/link publishing are implemented in code, including Meta-native scheduled publishing. The calendar currently aggregates saved drafts and Facebook posts. It is not yet a complete cross-platform scheduling engine: TikTok and YouTube publishing jobs are not yet represented as calendar entries, and no common background dispatcher exists.


## Audit remediation — 2026-11-02

- Corrected date-scoped calendar filtering so immediate Facebook posts (which have `scheduled_at = NULL`) are included using their creation timestamp.
- Added transactional activity-log entries for product/service create, update, delete, primary-offer changes, social-account disconnect, Instagram/TikTok/YouTube/Facebook connection callbacks, and Facebook/TikTok/YouTube publishing lifecycle changes.
- Facebook Page discovery now follows cursor pagination and returns `no_eligible_pages` rather than a false `connected` result when none of the returned Pages has `CREATE_CONTENT`.
- Added regression coverage for calendar date filtering, product audit events, social disconnect/connection audit events, Facebook Page pagination, and no-publish-permission outcomes.
- Latest backend verification in this environment: **129 passed, 1 skipped** using SQLite. PostgreSQL and frontend verification remain open.


## 2026-11-02 — Calendar interface vertical-slice progress
- Replaced the chronological-only calendar page with responsive month, week, and 30-day agenda views using the existing authenticated calendar API.
- Added period navigation, Today shortcut, day-to-agenda drill-down, per-day event previews, and explicit copy describing which provider events are currently included.
- No database/API contract change was needed; saved drafts and Facebook entries retain their existing backend source and timestamps.
- Verification limitation: frontend dependencies are not installed in this environment, so ESLint, TypeScript project checks, production build, and browser QA could not be run.
- Remaining calendar work: include TikTok/YouTube publishing jobs, add a common scheduling dispatcher, and implement provider-supported cancellation/rescheduling after live API verification.


## Calendar provider aggregation — 2026-11-02

- Extended the existing tenant-scoped calendar API to include TikTok and YouTube publishing jobs, using each job's creation timestamp and preserving `scheduled_at: null` so upload history is not misrepresented as scheduled content.
- Added regression coverage for both providers and date-scoped calendar queries.
- Updated calendar UI copy and API documentation to distinguish publishing history from actual scheduled posts.
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: pytest -q` — **130 passed, 1 skipped**; `python -m compileall -q backend/app backend/tests` — passed. This is SQLite verification only, not PostgreSQL or live-provider verification. Frontend build/browser QA remain outstanding.

## Scheduling milestone — 2026-11-02 (first vertical slice)
- Added provider-neutral `scheduled_posts` persistence and migration `20261102_0014`.
- Added organization-scoped create/list/cancel/reschedule APIs, owner/admin controls for lifecycle changes, activity logging, and central monthly scheduled-post quota enforcement.
- Added a database-backed due-post dispatcher with atomic claim transition, bounded retries, encrypted-token decryption, and a first Facebook Page text/link adapter. Run periodically with `python -m app.modules.posting.dispatcher`.
- Calendar feed now includes queued scheduled-post records. Added a frontend schedule form for connected Facebook Pages.
- TikTok/YouTube/Instagram background scheduling remains unavailable: their media transfer and provider-specific workflows need separate implementations. Dispatcher is not yet deployed as a managed recurring worker; configure a scheduler/worker process before relying on automatic dispatch.
- Verification in this authoring environment: **133 passed, 1 skipped** with SQLite test database; SQLite Alembic upgrade through `20261102_0014`, `alembic check`, and Python compileall passed. PostgreSQL, live Meta publishing, frontend lint/build, and browser QA remain unverified.


## Shared scheduling — Instagram photo slice (2026-11-02)

- Added nullable `media_url` to scheduled posts with Alembic migration `20261102_0015`.
- Instagram Login now requests `instagram_business_basic` and `instagram_business_content_publish`; connected-account scope metadata records both requested permissions. Existing Instagram connections must reconnect to grant publishing permission.
- Shared scheduling API accepts Instagram only with publishing scope and a public HTTPS image URL; Facebook behavior remains unchanged.
- Dispatcher creates an Instagram image media container and publishes it via `media_publish`, then records the provider ID in the shared calendar.
- Supports single-image professional-account photo posts only. Carousels, Reels, Stories, video scheduling, and TikTok/YouTube background dispatch remain outstanding.
- Tests added for scope/media validation and mocked two-step Instagram dispatch. Live Meta authorization, media fetch, app review, and provider publishing are not verified.


## Scheduling reliability increment — 2026-11-02

- Added retry scheduling timestamps and processing leases to shared scheduled posts (migration `20261102_0016`).
- Dispatcher now reclaims jobs abandoned in `processing` for more than 15 minutes, applies exponential retry backoff (1, 2 minutes, then capped at 60 minutes), and stops after three attempts.
- Fixed calendar history to preserve the actual provider for Instagram scheduled-photo publications (it previously labelled the calendar entry as Facebook).
- Added regression tests for retry timing, early-retry suppression, expired lease recovery, and provider identity.
- Verification is recorded with this delivery; live provider and production worker supervision remain unverified.

### Durable media foundation — 2026-11-02
- Added organization-scoped video asset upload, SHA-256 integrity metadata, private filesystem storage, and expiring HMAC-signed media delivery URLs.
- Added migration `20261102_0017_media_assets` and transactional activity logging for asset creation.
- TikTok scheduled publishing remains disabled. Object storage, durable worker transfer, provider URL ownership verification, cleanup/retention, resumable uploads, and live TikTok verification remain outstanding.

## TikTok background transfer foundation — 2026-11-02
- Added a reusable server-side TikTok Direct Post transfer adapter at `backend/app/modules/posting/tiktok_upload.py`. It validates the provider upload destination, streams stored media in sequential chunks, sets the required `Content-Length` and `Content-Range` headers, and refuses unsupported content types or empty files.
- Added mocked transfer tests covering sequential byte ranges, the final partial chunk, invalid upload destinations, and invalid media.
- This is a transfer primitive only: TikTok scheduled-post creation, worker orchestration, session initialization/status polling, and retry/idempotency reconciliation are not enabled yet. The upload URL must be initialized immediately before transfer because TikTok expires it after one hour.
- Verification: backend pytest — **145 passed, 1 skipped**. No live TikTok request, PostgreSQL run, or frontend build was performed.


## TikTok scheduled video publishing integration — 2026-11-02

- Added TikTok fields to scheduled posts, including an organization-owned media asset reference, duration, creator privacy choice, interaction settings, and provider publish ID.
- Scheduling API now accepts TikTok video schedules and verifies same-organization media ownership plus `video.publish` permission.
- Dispatcher initializes a fresh TikTok Direct Post session when due, checks creator privacy and duration constraints, streams the stored file through the existing chunked transfer helper, persists `publish_id`, and polls status on later runs.
- Unaudited TikTok clients remain restricted to `SELF_ONLY`.
- Migration: `20261102_0018_tiktok_scheduled_media.py`.
- Remaining: frontend scheduling UI, real PostgreSQL migration test, live TikTok provider verification, production shared/object storage, and robust handling of ambiguous provider timeouts.


## TikTok scheduling frontend vertical slice — 2026-11-02

- Extended `/schedule-post` with a Facebook/TikTok platform selector while preserving the Facebook scheduling workflow.
- TikTok scheduling loads the selected creator's privacy/interaction settings, validates video metadata and duration, requests explicit upload consent, uploads the file to private organization media storage, then creates a scheduled post referencing the returned media asset.
- Added typed frontend helpers for private media upload and expanded scheduled-post creation to the existing TikTok API contract.
- Updated calendar messaging to reflect TikTok background scheduling support.
- Verification for this increment is recorded in the delivery summary; live browser/provider tests remain outstanding.

## Authentication hardening increment — 2026-11-04

- Added server-side logout (per-token revocation by `jti`), sign-out-everywhere and password-change/reset session invalidation (`users.token_version`), change-password, and forgot/reset password with hashed one-time tokens, per-email and per-address rate limits, and SMTP email delivery.
- Frontend: sign-out now revokes the token on the server; new `/forgot-password`, `/reset-password`, `/security` pages; "Forgot password?" link on login.
- Verification: files compile (`py_compile`) and the token helpers were exercised in isolation. The authoring environment had no network, so FastAPI/SQLAlchemy/pytest and the frontend dependencies could not be installed: the new backend tests (`tests/test_auth_sessions.py`), the full existing suite, the migration, and the frontend lint/build have **not** been run.
- Next auth work: email verification, registration/login/password events in an audit log, Redis-backed limits, cookie-based sessions with CSRF review, refresh tokens.


## Phase 1 completion review — 2026-11-04

Reviewed the Stage A / Product 01 scope in `master-development-prompt.md` against the code. Implemented in code (not test-run here; see verification note above):
- Workspace management: owner-only rename (`PATCH /organizations/{id}`) and permanent delete with typed-name confirmation, protection of the user's last workspace, explicit child-record cleanup and best-effort media file removal; new `/workspace` settings page.
- Account management: `PATCH /auth/me` (display name) and a "Your account" section on `/security`.
- Drafts: `limit`/`offset` paging with a "Load more drafts" button; plain members can now delete only their own drafts (owners/admins any).
- Activity log: `entity_type` and `action_prefix` filters on the API.
- Workspace cap now configurable (`MAX_WORKSPACES_PER_USER`).
- Added the missing `backend/.env.example` and `frontend/.env.example` referenced by the README.

Still not implemented (deliberately deferred, tracked in known-issues): email verification and email change; pending-invitation management UI and invitation revocation; refresh tokens/cookie sessions; Redis-backed rate limits and Celery workers; Hybrid Brand Intelligence (needs live social ingestion); billing/upgrade flows; frontend automated tests; `package-lock.json` (needs network); object storage for media; logging of sign-ins/registrations and AI generations in the audit trail.


## Stage One remediation pass — 2026-11-04 (v0.2.5 working archive)

- Fixed missing Tailwind CSS v4 and `@tailwindcss/postcss` development dependencies; added `frontend/postcss.config.mjs`.
- Fixed Render Docker build context to `./backend`, matching the Dockerfile COPY paths.
- Added explicit Render `CORS_ORIGINS` and `MEDIA_PUBLIC_BASE_URL` settings. Production startup now rejects localhost CORS origins and missing/non-HTTPS public media API origins.
- Restricted shared schedule creation to workspace owners/admins. Scheduling is now an explicit approver action; ordinary members cannot directly create publish-queue jobs. This is not yet a draft-ID linkage workflow: an owner/admin's schedule action is the approval boundary.
- Reject TikTok video assets smaller than 5 MiB during upload, preventing a later worker-side failure.
- Added regression tests for schedule authorization, production configuration, and minimum media size; added an optional PostgreSQL registration-and-scheduling integration test.
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: pytest -q` — **178 passed, 2 skipped**. SQLite Alembic upgrade to `20261104_0020`, `alembic check`, and `python -m compileall -q app tests` passed. PostgreSQL integration test skipped because no `TEST_POSTGRES_URL` was available. Frontend `npm install` timed out; lint/build remain unverified.


## Stage One remediation pass — 2026-11-04 (v0.2.6)

- [x] Added nullable `scheduled_posts.draft_id` with a restrictive foreign key to `content_drafts`; existing historical schedule rows remain compatible.
- [x] Scheduling API now requires a draft ID, verifies tenant ownership and `approved` status, and rejects content that differs from the approved draft.
- [x] Scheduling frontend now loads approved drafts, requires selection, and submits the immutable approved text for Facebook and TikTok.
- [x] Draft edit/status-change and delete APIs reject changes while a linked schedule exists, preventing post-approval content mutation or deletion.
- [x] Profile confirmation now creates a transactional `profile.confirmed` activity event.
- [x] Added regression tests for approval enforcement, content tampering, linked-draft immutability, and profile confirmation activity.
- [x] Backend suite: 179 passed, 2 skipped on SQLite (actual local run); PostgreSQL remains unverified.
- [ ] Frontend lint/build remains unverified because frontend dependencies are not installed in this environment.
- [ ] Scheduler lease renewal, provider idempotency/ambiguous-timeout reconciliation, distributed rate limiting, token refresh parity, and Hybrid Brand Intelligence remain open.


## Stage One remediation pass — 2026-11-04 (v0.2.7)

- [x] Added a dedicated Instagram long-lived access-token refresh helper. Tokens within seven days of expiry are refreshed using Instagram Login's `ig_refresh_token` flow; successful encrypted-token and expiry updates are committed before publishing continues. Already-expired tokens fail with a reconnect instruction rather than attempting an unsupported refresh.
- [x] Integrated the refresh helper into the shared Instagram scheduled-post dispatcher. Facebook Page credentials remain on their separate token model and are not incorrectly sent through Instagram's refresh endpoint.
- [x] Added conservative duplicate-risk handling for Facebook feed publishing and Instagram `media_publish`: transport failures/timeouts and provider 5xx responses after the publish request begins are marked failed with an explicit uncertain-outcome warning instead of being automatically retried. Instagram media-container creation failures remain retryable because they have not yet reached the public publish operation. TikTok continues to use its provider publish ID/status polling path.
- [x] Corrected the dispatcher lease comment to match the configured 60-minute lease. This is a documentation correction only; lease heartbeat/renewal is still open.
- [x] Added seven unit tests for Instagram token refresh boundaries, persistence, expired-token handling, provider guard, and ambiguous publish-error classification.
- [x] Version metadata advanced to v0.2.7.
- [x] Backend suite: **186 passed, 2 skipped** using SQLite (actual local run).
- [ ] PostgreSQL application integration remains unverified; this environment has no psycopg driver or PostgreSQL server.
- [ ] Frontend lockfile/lint/build remain unverified. npm package-lock generation was attempted online and offline; online registry access timed out and the offline cache did not contain the Tailwind PostCSS package metadata. No fabricated lockfile was added.
- [ ] Scheduler lease heartbeat, distributed rate limiting, broader credential lifecycle work, Hybrid Brand Intelligence, and YouTube browser-closure/background recovery remain open.


## Post-report increment — YouTube processing poller (2026-11-04)

- [x] Added an independently invokable worker (`python -m app.modules.posting.youtube_worker`) that polls YouTube processing status for jobs with a verified video ID and persists provider state.
- [x] Added unit tests for successful, processing, and failed provider status mapping.
- [ ] Browser transfer interruption recovery remains open; the worker cannot recover a session before YouTube has returned and the application has verified a video ID.
- [ ] Production worker supervision and live YouTube verification remain open.
- Verification: `DATABASE_URL=sqlite:///./test.db pytest -q` — **190 passed, 2 skipped**; `python -m compileall -q app tests` — passed.

## Scheduler lease hardening — 2026-11-04

- [x] Added `lease_token` and `lease_expires_at` to scheduled posts (migration `20261104_0022`).
- [x] Dispatcher claims now assign a unique owner token and a 60-minute expiry; stale recovery uses the renewable expiry while retaining compatibility with pre-migration processing rows.
- [x] Added an independent-session heartbeat every 30 seconds during provider work. Heartbeats update only rows still owned by the same token; a stale worker cannot renew a lease claimed by another worker.
- [x] Added ownership checks before successful finalization and before persisting exception/retry state, preventing stale workers from overwriting a newer claim.
- [x] Verification: Python compileall passed; backend suite **190 passed, 2 skipped** on SQLite; Alembic upgrade to `20261104_0022` passed on SQLite.
- [ ] PostgreSQL concurrency behavior and real multi-worker/provider failure scenarios remain unverified.
- [ ] Distributed rate limiting, provider-side idempotency/reconciliation, and other listed production gaps remain open.

## Scheduler ambiguity regression coverage — 2026-11-04
- Added parameterized regression coverage proving the Facebook dispatcher does not automatically retry when a publish POST ends in a transport timeout or an HTTP 5xx response. Both outcomes can occur after the provider accepted the post, so the job is marked failed with an explicit uncertain-outcome message for manual verification.
- The behavior is implemented in the dispatcher already; this increment locks it down with tests rather than claiming exactly-once delivery. A provider-side idempotency/reconciliation API is still needed for safe automatic recovery.
- Verification (earlier authoring run): focused scheduler regression tests plus rate-limit tests — **6 passed**; complete scheduling test module — **12 passed**; Python compileall passed. Full backend suite was started but exceeded the execution time limit before completion. PostgreSQL, live Meta publishing, and frontend build remain unverified.

## Instagram ambiguity coverage and open verification — 2026-11-04
- [x] Added Instagram tests: no retry after a timeout/5xx at `media_publish`; retry after a failure creating the container or a 4xx at `media_publish`.
- [ ] Not yet executed: the new Instagram tests and the rewritten limiter tests need a real `pytest` run (only the limiter tests were run, through a stand-in harness).
- [ ] Re-run the full backend suite and replace the stale "190 passed, 2 skipped" figure with the new result.
- [ ] Generate and commit `frontend/package-lock.json` on a networked machine, then run lint and build.

## Code review pass — 2026-11-04
- [x] Fixed: signed-media 500 on non-ASCII signatures; percent-encoded upload filenames; cancel/reschedule race with the dispatcher; scheduled-post responses leaking worker internals; stored content now exactly the approved draft.
- [ ] Not executed here: the new media and scheduling tests. Run the full backend suite and update the stale "190 passed" figure.
- [ ] Review not yet covered: social OAuth callbacks in depth, TikTok/YouTube publishing endpoints, the frontend (auth token storage, pages), migrations against PostgreSQL.

## Follow-up code review — 2026-11-04
- [x] Closed a duplicate-post risk: after a Facebook/Instagram publish request begins, malformed provider response data, a missing post ID, or a SQLAlchemy persistence failure is now treated as an ambiguous outcome and is not automatically retried. Explicit provider 4xx responses remain definitive rejections.
- [x] Added regression coverage for malformed response/missing-ID and database-error classification.
- [x] Focused backend verification: **86 passed** across Instagram token refresh, media validation, rate limiting, scheduling, YouTube worker, auth sessions, phase-one completion, and organization tests.
- [x] Python compileall passed; SQLite Alembic upgrade reached `20261104_0022`; Alembic schema check reported no new operations.
- [ ] Full backend suite remains unverified: the default run cannot import the unavailable `psycopg` package; SQLite-backed full-suite attempts exceeded the execution time limit.
- [ ] Frontend lint/build, PostgreSQL concurrency, live social-provider behavior, and browser QA remain unverified.
- See `review-2026-11-04.md` for the complete review summary and limitations.


## 2026-11-04 — Google account sign-in

- Added Google OpenID Connect sign-in on the login page (`openid email profile` only).
- Added backend authorization-code callback with state-cookie and nonce validation, Google ID-token signature/issuer/audience/expiry verification, and verified-email enforcement.
- Added a provider-subject identity table and Alembic migration `20261104_0023`.
- New Google sign-ins automatically receive a starter workspace; existing accounts with the same Google-verified email are linked.
- Added frontend callback handling and setup instructions in `docs/google-sign-in.md`.
- Google sign-in uses dedicated `GOOGLE_LOGIN_*` credentials, separate from the Google OAuth client used for YouTube publishing.
- Verification: Python compilation passed; auth/session tests passed (28); migration upgrade and `alembic check` passed on SQLite. Full backend suite began but exceeded the execution window; frontend build/lint and live Google-provider handshake remain unverified.


## Stage-one review + social sign-in — 2026-11-04
Hardened Google sign-in, added WhatsApp one-time-code sign-in, `/auth/providers`, a non-blocking "complete your profile" prompt, and fixed dashboard layout bugs and lint-breaking JSX. New backend tests and migration `20261104_0024` are unrun; frontend lint/build/browser QA still outstanding. See `known-issues.md`.

## Follow-up implementation increment — requested screenshot items (2026-11-04)

- [x] Workspace invitation administration API: owner/admin list invitations; owner/admin revoke pending invitations; accepted invitations remain immutable history; tenant scope and role checks are enforced; revocations are activity-logged.
- [x] Workspace settings UI: invite teammates, choose permitted role, view invitation history/status, and revoke pending invitations. Admins can invite members; only owners can invite admins or rename/delete the workspace.
- [x] Redis-backed shared rate-limiter implementation for login, password reset/change, WhatsApp verification/request, and AI caption/video generation. Configure `REDIS_URL` to enable it; local bounded limiter remains the development/test fallback. Redis errors intentionally do not silently fall back when Redis is configured.
- [x] Billing discovery/readiness endpoints expose the central placeholder plan catalog and explicitly report that prices, checkout, and webhooks are not live. Paystack credential settings are documented, but no charge can be initiated.
- [x] Added regression tests for invitation administration and billing readiness.
- [ ] Email verification: `email_verified_at` exists in the user model, but verification-token issuance, delivery, confirmation UI, and enforcement are not implemented.
- [ ] Hybrid Brand Intelligence: post ingestion/latest-20 sync, evidence/provenance storage, AI analysis, conflict detection, and review UI remain unimplemented. Official provider access/scope verification is required before syncing.
- [ ] Billing completion: subscription/customer persistence, pricing approval, Paystack checkout, signed/idempotent webhooks, invoice/renewal/cancellation lifecycle, and frontend billing UI remain outstanding. Readiness endpoints are not a substitute for these.
- [ ] New database migration was not required for this increment: invitation persistence already exists in migration `20261104_0025`; Redis rate-limit state is external; billing is deliberately read-only and does not persist subscriptions.
- [ ] Frontend lint/build and browser checks remain unverified because frontend dependencies are not installed in this runtime.

## Verification for this increment

- `python -m compileall -q backend/app backend/tests`: passed.
- `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_organizations.py tests/test_billing_readiness.py tests/test_rate_limit.py`: **30 passed**.
- Full backend suite was attempted but exceeded the 120-second execution window; no full-suite pass is claimed.
- PostgreSQL migration compatibility, live Redis behavior, SMTP delivery, Paystack, social-provider APIs, and frontend browser behavior were not tested.


## Brand Intelligence backend increment — 2026-11-04

- [x] Added organization-scoped social post observation and reviewable brand analysis models.
- [x] Added Alembic migration `20261104_0027`.
- [x] Added tenant-scoped list/manual-entry/analyze/list-analysis/review/delete API endpoints.
- [x] Manual observations are labelled unverified; they cannot be confused with provider-fetched posts.
- [x] AI proposals preserve source observation IDs and conflicts and never overwrite confirmed business profile facts.
- [x] Added activity-log entries for observation and analysis changes.
- [x] Added API contract documentation and regression test for tenant isolation and review lifecycle.
- [ ] Official provider adapters, automated latest-20 sync, durable sync jobs/retries, and frontend review interface remain next work.
- [ ] Live provider and AI API verification remain outstanding.

## Durable Brand Intelligence synchronization — 2026-11-04 (increment 6)

- [x] Added durable `brand_sync_jobs` persistence and Alembic migration `20261104_0028`.
- [x] Added owner/admin API to enqueue sync jobs with HTTP 202, deduplicate active jobs, and inspect organization-scoped job status/history.
- [x] Added database-backed worker that reuses the existing provider adapters and synchronous upsert/activity-log path; manual immediate sync remains compatible.
- [x] Added automatic latest-20 synchronization queueing for connected accounts that have never synced or whose last successful sync is at least six hours old.
- [x] Added bounded retry behavior (three attempts, 1/2-minute retry delay for server/provider failures), terminal handling for permission/account errors, and recovery of jobs left running for more than 30 minutes after a worker interruption.
- [x] Automatic job creation is activity-logged; sync completion continues to use the existing activity-log entry.
- [x] Verification: Brand Intelligence, sync worker, Instagram, Facebook, TikTok, YouTube, and social OAuth focused suites — **33 passed**, then worker/Brand Intelligence suite — **8 passed**; Python compileall passed.
- [x] Alembic SQLite upgrade through `20261104_0028` and `alembic check` — no schema drift detected.
- [ ] PostgreSQL 16 behavior, multi-worker contention/leases, live social APIs, frontend job-status UI, full backend suite, and production worker supervision remain unverified.

## Paystack server-side transaction verification helper — 2026-11-04 (Increment 9)

- [x] Added `backend/app/integrations/payments/paystack_transactions.py` to retrieve transaction details from Paystack's server-side `GET /transaction/verify/:reference` endpoint using the secret key.
- [x] Added strict validation of the provider response envelope and transaction data shape; provider/network/HTTP errors are surfaced as a safe integration error.
- [x] Added a pure expected-transaction comparison for successful status, exact reference, exact amount in minor units, currency, and optional customer email.
- [x] Added tests for authorization header, URL-encoded references, unsuccessful/malformed responses, HTTP/network errors, missing configuration, successful matching, and mismatched payment data.
- [x] Verification: Paystack transaction, signature, billing-readiness, and plan tests — **30 passed** using mocked Paystack HTTP responses and SQLite test configuration; Python compilation passed.
- [ ] No checkout initialization, pending transaction persistence, webhook route/event processing, subscription persistence/lifecycle, or plan activation is implemented. The helper is not called by a public endpoint and cannot grant access.
- [ ] Owner-approved prices and billing policy, live Paystack test-mode verification, PostgreSQL 16, frontend build/browser QA, and production integration remain outstanding.


## Increment 10 — Paystack persistence schema foundation (2026-11-04)

**Implemented:**
- Added SQLAlchemy models for `PaymentTransaction`, `Subscription`, and `PaymentWebhookEvent`.
- Added migration `20261104_0029` to create the three tables with organization ownership, unique transaction references, unique provider transaction IDs, one subscription row per organization, unique webhook event keys, and useful lookup indexes.
- New payment attempts default to `pending`; new subscriptions default to `free` / `inactive`; webhook receipts default to `received`.
- Webhook storage retains a SHA-256 digest and event metadata, not the raw payment payload.
- Added tests for persistence defaults and uniqueness/idempotency constraints.

**Verification performed:**
- `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest tests/test_payment_persistence_models.py tests/test_paystack_signatures.py tests/test_paystack_transactions.py tests/test_billing_readiness.py tests/test_plans.py -q` — **34 passed in 2.18s**.
- `python -m compileall -q app tests` — passed.
- Full Alembic upgrade from empty SQLite database through `20261104_0029` — passed.
- `alembic check` against that SQLite database — no pending model changes.

**Not verified:** PostgreSQL 16, frontend, live Paystack, production webhook delivery, payment lifecycle, and any customer charge.

**Important:** This increment adds schema only. It does not add routes, initialize payments, process webhooks, activate subscriptions, or enable checkout. Prices remain unapproved.


## Increment 11 — payment provider architecture and managed pricing (2026-11-04)

- [x] Added a provider-neutral payment contract and registry. Paystack is the initial integration; PayPal and Flutterwave are registered as future providers, not active.
- [x] Added a Paystack hosted Checkout adapter that sends trusted server-supplied amounts/currencies and validates the returned checkout URL/reference.
- [x] Added migration `20261104_0030` with seeded Standard/Premium prices in NGN/USD for monthly and annual billing. Prices are stored as minor-unit integers. Annual pricing equals ten monthly payments.
- [x] Added platform-owner-only price catalog read/update APIs guarded by `PLATFORM_ADMIN_EMAILS`, plus append-only price-change history.
- [x] Public plans endpoint now reads the database-backed catalog. Existing subscriptions are not modified by price edits.
- [x] Verification: focused billing/payment suite — **40 passed** with SQLite and mocked Paystack HTTP. Python compilation passed. Alembic full upgrade, latest migration downgrade and re-upgrade passed on SQLite.
- [ ] Platform-admin price editor is implemented at `/platform/billing-prices` but has not been browser-tested. Customer checkout orchestration, webhook endpoint/processing, verified subscription activation, renewal/cancellation/refund lifecycle and customer billing UI remain outstanding. Checkout/webhooks remain disabled.
- [ ] PostgreSQL 16, real Paystack test/live mode, merchant Google Pay activation/checkout, frontend install/build and browser/mobile QA remain unverified. Full backend pytest reached 100% output but did not terminate within 240 seconds; do not count it as a passing full-suite run.
- [ ] PayPal and Flutterwave are future integrations. AI-provider cost monitoring/alerts are not implemented.


## Customer billing vertical slice — 2026-11-04 (Increment 12)

- [x] Added `billing_interval` to payment transaction snapshots with migration `20261104_0031`.
- [x] Added owner/admin-only customer checkout initialization. The backend selects an enabled catalog price, persists the pending payment snapshot and activity record, then calls the Paystack hosted-checkout adapter. No amount is accepted from the browser.
- [x] Added authenticated browser-return verification. The server verifies reference, amount, currency, customer email and success status directly with Paystack before fulfillment.
- [x] Added signed `POST /api/v1/billing/webhooks/paystack`, raw-body signature verification, durable minimal receipt, idempotency key, and server-to-server verification for `charge.success`. Duplicate processed events do not grant a second subscription period.
- [x] Added atomic initial subscription activation, organization plan update and activity log. Same-plan paid periods extend from the current end date; plan changes take effect immediately.
- [x] Added customer `/billing` page and `/billing/return` status page; added Billing to application navigation including mobile navigation.
- [x] Updated `docs/paystack-billing.md` with API contracts, configuration, provider status, operational limitations and remaining work.
- [x] Focused billing/payment tests: **31 passed** with SQLite and mocked provider calls. Python compileall passed.
- [ ] Frontend dependencies are absent; lint, TypeScript, Next build and browser/mobile QA remain unverified. PostgreSQL 16, live Paystack and live Google Pay remain unverified. File-backed SQLite migration upgrade/downgrade/re-upgrade passed.
- [ ] Automatic recurring renewals, cancellation, refunds/disputes, automatic webhook reconciliation and payment settlement reconciliation remain outstanding. Checkout is not production-ready until real test-mode verification and PostgreSQL checks are completed.

## Platform administration and billing operations — 2026-11-04 (Increment 13)

- [x] Added a platform-owner-only customer directory with search, active/suspended filtering, pagination, customer detail, linked organizations, subscription snapshots, and recent payment transactions.
- [x] Added account suspension/reactivation. Suspension increments `token_version`, invalidating existing sessions. Platform administrators cannot suspend themselves or another allowlisted platform administrator.
- [x] Added append-only `platform_admin_audits` records for global account status changes; migration `20261104_0032`.
- [x] Added platform overview metrics and a billing operations view showing safe Paystack configuration state, test/live/unknown key mode, recent transactions, and webhook outcomes. No secrets are returned.
- [x] Added responsive `/platform` admin page and navigation link for verified platform-owner accounts.
- [ ] Live Paystack test-mode checkout, webhook delivery, Google Pay eligibility, and production callback/webhook routing still require the owner's merchant account and deployed environment. The dashboard reports configuration; it does not claim to perform a live provider test.
- [ ] PostgreSQL 16 migration verification, frontend dependency install, TypeScript/lint/production build, browser/mobile QA, subscription cancellation/renewal/refund/dispute/reconciliation, and failed-webhook replay/recovery remain outstanding.
- [x] Focused verification: platform-admin and billing regression tests — 13 passed on SQLite with mocked provider behavior; Python compilation passed. Full suite and frontend build were not run.

## Increment 14 — manual Paystack webhook recovery (2026-11-04)

- Added platform-owner-only recovery for failed Paystack `charge.success` webhook receipts and stale `processing` receipts older than ten minutes.
- Recovery always performs fresh server-side Paystack transaction verification and uses the shared idempotent fulfillment service; it cannot activate from webhook payload data alone.
- Added audit records for recovery outcomes, a dashboard retry control for failed charge-success events, and a visible recent platform-admin audit history.
- Verification: focused platform-admin + billing + Paystack checkout/signature/transaction tests — **36 passed** on SQLite with mocked Paystack behavior; Python compilation passed.
- No schema migration was required. PostgreSQL 16 locking/concurrency, frontend production build/browser QA, and live Paystack test-mode checkout/webhook verification remain outstanding.


## Payment reconciliation — Increment 15 (2026-11-04)

- [x] Added bounded reconciliation of pending Paystack transactions older than a configurable safe threshold (default 10 minutes).
- [x] Reuses fresh server-to-server verification and the existing idempotent, row-locked subscription fulfillment service.
- [x] Added platform-owner endpoint and `/platform` action to run a bounded reconciliation pass; action is audited.
- [x] Added CLI scheduler entry point `python -m app.jobs.reconcile_payments` for a hosting cron/scheduled-job runner.
- [x] Focused tests: **13 passed** across reconciliation, platform admin, and checkout fulfillment using SQLite/mocked Paystack; Python compileall passed.
- [ ] Configure the actual hosting scheduler; no in-process scheduler is started automatically. PostgreSQL concurrency, live Paystack test mode, frontend build/browser QA and deployment remain unverified.


## Subscription lifecycle management — 2026-11-04 (Increment 16)

- [x] Owners can schedule cancellation at the paid period end and reverse it before that date.
- [x] Added tenant-scoped recent payment history to customer billing.
- [x] Added subscription lifecycle processor: cancelled plans end at period boundary; non-cancelled subscriptions enter configurable past-due grace; expired subscriptions downgrade organization to Free.
- [x] Added `BILLING_GRACE_PERIOD_DAYS` (default 3, range 0–14) and scheduled CLI `python -m app.jobs.process_subscription_lifecycle`.
- [x] Platform admin customer details/overview now include past-due, cancelled, expired and grace-period subscription information.
- [x] Migration `20261104_0033` adds grace and cancellation timestamps.
- [x] Verification: 18 focused tests passed; Python compile passed; SQLite migration upgrade/downgrade/re-upgrade and Alembic check passed.
- [ ] Configure the hosting scheduler for the lifecycle CLI.
- [ ] Automatic recurring payment collection, renewal reminders, refunds/disputes, PostgreSQL 16, frontend build/browser/mobile QA and live Paystack/Google Pay verification remain outstanding.


## Increment 17 — Paystack recurring-charge adapter foundation — 2026-11-04

- [x] Added a Paystack adapter method for `transaction/charge_authorization` with server-side amount/currency/reference inputs and validation.
- [x] Added mocked HTTP tests for successful charge request construction, secret-key authentication, returned reference validation path, unsupported currencies and invalid references.
- [x] Verification: Paystack checkout, billing fulfillment, subscription lifecycle and payment reconciliation tests — **17 passed**; no database migration required.
- [ ] This is an adapter primitive only. No authorization codes are stored, no recurring charge is scheduled, and no subscription is automatically renewed.
- [ ] Next: explicit recurring consent, encrypted reusable authorization storage, durable renewal-attempt records, verification/webhook fulfillment, 3DS challenge handling, bounded retry policy, renewal notices, customer billing UI, and Paystack test-mode validation.
- [ ] Live Paystack, PostgreSQL 16, frontend build/browser QA and deployment remain unverified.


## Increment 18 — recurring consent and encrypted authorization storage — 2026-11-04

- Added an optional customer consent checkbox to `/billing` to prepare a reusable authorization for possible future renewals; the UI clearly states automatic renewal is not active yet and that the customer will be notified before activation. Unchecked checkout remains a one-time payment.
- Checkout API accepts `recurring_consent` (default false) and stores a server-generated consent timestamp, version and wording snapshot with the pending payment. Consent is also included in Paystack metadata for traceability, but the server-side payment record is authoritative.
- On server-verified successful payment, only a Paystack authorization explicitly marked `reusable: true` and attached to a payment with recorded consent is eligible for storage. The authorization code is encrypted with a dedicated `BILLING_AUTHORIZATION_ENCRYPTION_KEY`; exact checkout email is retained for provider compatibility. Limited card display metadata only; no PAN/CVV.
- Added migration `20261104_0034_recurring_authorization_consent.py`. Existing rows remain valid and default to no reusable authorization.
- Verification: focused checkout/Paystack/lifecycle/reconciliation tests **20 passed** using SQLite and mocked provider responses; Python compile passed; file-backed SQLite Alembic upgrade/downgrade/re-upgrade and `alembic check` passed. Frontend dependencies are absent; PostgreSQL 16 and live Paystack remain unverified.
- Still not implemented: durable renewal-attempt records, scheduler/worker charge execution, recurring charge server verification and atomic fulfillment, 3DS/customer challenge flow, bounded retries, renewal notices, customer-facing auto-renew toggle/revocation, live Paystack test-mode authorization validation, PostgreSQL concurrency tests and production deployment. Automatic charging remains off.


## Customer billing authorization management — 2026-11-04 (Increment 21)

- [x] Added `PaystackProvider.deactivate_authorization`, calling Paystack `POST /customer/authorization/deactivate` with the authorization code and server-side secret key.
- [x] Added owner-only `POST /api/v1/billing/organizations/{organization_id}/subscription/authorization/revoke`. It decrypts the saved authorization only on the server, requests Paystack deactivation, and clears local ciphertext/card display metadata only after Paystack confirms success.
- [x] If Paystack is unavailable, rejects deactivation, or returns an ambiguous failure, the API does not claim success and retains the encrypted authorization for safe follow-up.
- [x] The customer subscription response now exposes only safe flags and card display metadata (`authorization_saved`, last four digits, card type, and whether consent evidence exists); encrypted authorization bytes and the authorization code are never returned.
- [x] Connected `/billing` with a saved-payment-method panel and owner-only deactivation control. The confirmation explains that revoking the payment method does not cancel current paid access.
- [x] Historical consent evidence remains recorded after revocation; reusable authorization and its associated card display metadata are cleared.
- [ ] Paystack 3DS/OTP renewal challenge completion, renewal email notices, bounded retries, PostgreSQL 16 verification, live Paystack test-mode deactivation, and frontend browser/build QA remain outstanding. Keep `BILLING_RENEWALS_ENABLED=false`.

### Increment 21 verification

- `cd backend && DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_paystack_checkout.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py` — **24 passed in 2.54s** using SQLite and mocked Paystack calls.
- `python -m compileall -q app tests migrations` — passed.
- No schema migration was required. Frontend dependencies are absent; Next lint/typecheck/build/browser/mobile QA were not run. PostgreSQL 16 and live Paystack were not tested.


## Increment 25 — provider-directed retry and managed billing operations — 2026-11-05

- [x] Paystack adapter recognizes only explicit card-regulator retry responses (`retry_by` or the documented “cannot be fulfilled until X minutes” response). Generic failures do not become retryable.
- [x] A renewal can enter `retry_scheduled` only when the provider supplies a future retry window no more than 24 hours away. One delayed re-entry maximum is allowed for that subscription period; the existing payment reference is retained.
- [x] Ambiguous network outcomes remain verification-only. OTP/3DS, ordinary declines, insufficient funds, generic HTTP failures and verification mismatches are not automatically recharged.
- [x] Added migration `20261104_0039_provider_directed_renewal_retry.py` with `retry_at` and `retry_count`.
- [x] Added `python -m app.jobs.run_billing_maintenance`, a bounded single-entry scheduler that processes notifications, verification reconciliation, provider-directed retry, due renewals (only when enabled), and subscription lifecycle transitions in a safe order. It emits structured JSON and returns a non-zero exit code on infrastructure failure.
- [x] Added a Render cron service in `backend/render.yaml` to run the maintenance command every five minutes. Billing notification and automatic renewal flags are explicitly false in the blueprint.
- [x] Added `python -m app.jobs.check_billing_readiness`; it checks DB connectivity and can send one controlled SMTP test email only when `--email-to` is explicitly supplied.
- [x] Added `docs/operations/billing-scheduler.md` with deployment variables, alerting, runbook, retry limits and SMTP smoke-test instructions.
- [x] SMTP transport behavior is covered with a mocked SMTP handshake test; real SMTP credentials/inbox delivery still require owner-side verification.
- Verification: focused billing/configuration/PostgreSQL-gated set — **65 passed, 3 skipped**; Python compileall passed; SQLite migration upgrade/downgrade/re-upgrade and `alembic check` passed.
- Not verified: PostgreSQL 16 concurrency, live Paystack regulator response/retry behavior, actual SMTP delivery, Render cron execution/alerts, frontend build and browser/mobile QA.
- `BILLING_RENEWALS_ENABLED=false` and `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` remain defaults.

## Increment 31 — dashboard visual redesign (2026-11-05)

Redesigned the authenticated home/dashboard to follow the supplied desktop light-mode visual direction: welcome hero, compact capability shortcuts, four live workspace metrics, connected social accounts, AI content-studio callout, upcoming publications, and recent drafts. Retained the existing authentication/session verification, organization switching/creation, theme toggle, workspace search, profile-completion prompt, data-fetching APIs, retry behavior, and mobile navigation. Dashboard figures remain derived from the existing drafts, social-account, and calendar APIs; no fabricated analytics or unsupported lead/email modules were added. Added responsive layouts for narrower screens and color-filled icon tiles with white glyphs, using the existing purple/blue identity and restrained supporting accents.

**Verification:** Frontend dependencies are still absent (`frontend/node_modules` and `package-lock.json` are not present), so ESLint, installed-project TypeScript validation, Next.js build, and browser/mobile visual QA could not be run. The source was inspected after editing; this is not a claim that the frontend build passes. Existing known frontend verification blockers remain in force.

## Increment 37 — branded login page visual refresh (2026-11-07)

Updated `/login` with a deep purple outer canvas, darker purple brand/story panel on desktop, and pale lavender sign-in surface. Added restrained decorative glow/orbit elements and a mobile-first brand header. Existing email/password, demo sign-in, social sign-in, error handling, redirect validation, and account links are preserved. Palette tokens are centralized in `frontend/src/app/globals.css`, including fixed form text colors for contrast across the app's theme modes. No authentication or backend behavior changed. See `increment-37-login-page-visual-refresh-2026-11-07.md`.

**Verification:** `git diff --check` and source inspection only. Frontend dependencies remain absent; ESLint, TypeScript, Next.js build, and browser/mobile QA were not run.


## Pre-deployment review — 2026-11-07

- Refined the purple-glass visual system across login, registration, password recovery, password reset, email verification, and WhatsApp sign-in. Removed the authentication-page radial/orbit decoration entirely.
- Hardened the login `next` redirect to reject external/protocol-relative destinations after URL normalization. Added a production build guard for a valid HTTPS `NEXT_PUBLIC_API_BASE_URL`, and ensured `/verify-email` renders outside the authenticated navigation shell.
- Tightened production backend settings: require PostgreSQL, HTTPS frontend/CORS/media URLs, SMTP, and a non-placeholder email sender.
- Confirmed dashboard KPI cards use horizontal icon/text alignment and compact two-column mobile sizing.
- Python compileall and auth source/visual regression checks passed. Full backend and frontend automated checks could not run: `pyotp`/`redis` are missing locally, package-index access is unavailable, `npm install` timed out, and no frontend lockfile is present.
- **Release status remains NOT production-ready.** PostgreSQL 16 migration/integration tests, frontend lockfile/lint/typecheck/build/browser QA, SMTP, live social-provider workflows, Paystack test-mode workflows, cron monitoring, backups/restore, and staging deployment remain mandatory release gates. See `docs/project-management/pre-deployment-review-2026-11-07.md` for the exact checklist.

## Increment 38 — dashboard profile control and KPI polish (2026-11-07)

Replaced the separated dashboard initials avatar and workspace-chevron control with one integrated purple profile/workspace trigger. Its dropdown now presents account identity, business profile, workspace settings, account security, workspace switching/creation, and sign-out in one compact menu. Escape and outside-pointer dismissal are supported. Preserved existing auth/session, workspace creation/switching, and sign-out behavior. Rechecked KPI cards: icons remain on the left, metrics and labels on the right, and chevrons are spaced to avoid crowding labels on narrow mobile screens. Dashboard KPI and panel icon references were checked against the shared SVG icon map. See `increment-38-dashboard-profile-control-and-kpi-polish-2026-11-07.md`.

**Verification:** Source-level structural checks and icon-map audit only. The extracted archive has no frontend `node_modules` or npm lockfile, so installed-project typecheck, ESLint, Next.js build, Vitest, and browser/mobile interaction QA remain outstanding. Do not treat the UI as fully runtime-verified until those checks are completed.

## 2026-11-07 — Increment 43 platform administration expansion

Added `/admin/login` entry point, successful password-login telemetry (`platform_login_events`), global organization activity endpoint, customer detail enrichment (business profile metadata, social accounts, recent drafts/scheduled posts, usage and login history), and currency-separated financial/usage analytics. See `increment-43-platform-intelligence-financial-monitoring-2026-11-07.md` for API contracts, migration, known gaps and handover. Financial costs/profit are intentionally marked unavailable until cost, refund and chargeback data sources are configured.

Increment 43 follow-up: added a manual, administrator-verified operating-cost ledger with `platform_cost_entries` (migration `20261107_0044`) and frontend entry form. Financial reporting now displays recorded expenses by currency while explicitly withholding net-profit claims until refunds, chargebacks and all vendor costs are accounted for.

## Increment 44 — provider-aware platform login telemetry (2026-11-07)

- [x] Successful password, Google and WhatsApp sign-ins now record the provider/method in the existing `platform_login_events` table.
- [x] A shared best-effort helper keeps telemetry database failures from interrupting successful authentication.
- [x] No migration required; existing admin login-history/customer inspection surfaces already display the method field.
- [x] Privacy boundaries retained: no raw IP, password, OAuth token, WhatsApp code, phone number, email or provider subject is stored in this telemetry event.
- [ ] Failed-login telemetry is deferred until aggregation, retention and privacy controls are designed.
- [ ] Provider integration tests, PostgreSQL verification, frontend build and browser QA remain required.

See `increment-44-provider-aware-login-telemetry-2026-11-07.md`.

## 2026-11-07 — Increment 45: AI token metering
- Added provider-reported token metering for OpenAI caption, video-script and AI brand-analysis requests.
- Added platform admin grouped AI usage analytics and financial-panel visibility by model/feature.
- Added optional explicit per-million-token USD rates; cost remains unknown unless configured (no guessed rates).
- Migration: `20261107_0045_ai_usage_records.py` (after `20261107_0044`).
- Validation: `python -m compileall -q backend/app backend/migrations` passed; Alembic history and full SQLite migration upgrade through `20261107_0045` passed. Targeted pytest collection is blocked because this environment lacks `pyotp`.


## Increment 46 — Refund and chargeback monitoring

- [x] Payment adjustment ledger and migration 0046.
- [x] Signed Paystack refund, dispute-created and dispute-resolved webhook event handling.
- [x] Admin adjustment list API and financial summary.
- [x] Admin UI displays refunds and dispute states separately.
- [ ] Paystack sandbox payload verification and automated webhook tests.
- [ ] Unmatched-event review queue, provider backfill, fee/reversal reconciliation.
- [ ] Final net revenue/profit calculation remains blocked until overlapping adjustments and full expenses are reconciled.


## Increment 47 — Platform administrator MFA
- [x] Require enrolled TOTP for platform-admin API access.
- [x] Require password plus TOTP during sign-in for enrolled platform administrators.
- [x] Prevent OAuth/WhatsApp sign-in from bypassing MFA for enrolled platform administrators.
- [x] Invalidate existing sessions when MFA is enabled.
- [x] Document rollout and remaining security work.
- [ ] Implement granular delegated administrator roles and permissions.
- [ ] Implement recovery codes and dual-control MFA reset.

### Increment 48 — delegated platform-admin roles

Implemented a database-backed delegated role system (`support`, `finance`, `operations`, `viewer`) with server-side permission dependencies, owner-only role assignment/revocation, audit entries, mandatory MFA for delegated admins, and an owner-facing role management panel. Billing price changes remain owner-only. Migration: `20261107_0047` (parent `20261107_0046`). Full automated integration tests and production frontend build remain to be run in the dependency-complete CI environment.

## Increment 49 — administrator security and email campaigns (2026-11-07)

Added owner-only administrator security review (recent sign-in records, identifiable failed sign-ins, IP/user-agent telemetry and account-wide session revocation) plus owner-controlled email announcements to registered accounts with verified email addresses. Campaigns persist recipient snapshots and sent/failed results, require SMTP configuration and are delivered in background batches. Migration `20261107_0048`. SMTP acceptance does not guarantee inbox delivery; process-local background tasks are not a durable queue, and unsubscribe/bounce handling plus IP retention policy remain production follow-ups. See `increment-49-admin-security-and-email-campaigns-2026-11-07.md`.

## Increment 50 — durable platform announcement delivery (2026-11-07)

- Replaced process-local background campaign sending with a persisted recipient queue and a repeatable single-instance scheduler CLI.
- Added bounded exponential SMTP retries (up to three attempts), owner retry control, campaign analytics API, per-recipient unsubscribe tokens, global email suppression, and a public unsubscribe page.
- Migration `20261107_0049_email_queue_retries_unsubscribe.py` follows `0048`.
- SMTP acceptance is still not proof of inbox delivery. Bounce/complaint provider webhooks, idempotent provider message delivery, open/click analytics and distributed worker leasing remain outstanding.
- Verification: Python compilation and fresh SQLite migration upgrade through `0049` passed. Full tests, frontend build, PostgreSQL and live SMTP are unverified.

## Latest increment — 2026-11-07 (Increment 51)

- Added Resend as an optional API provider for platform announcement campaigns, with stable per-campaign/per-recipient idempotency keys and persisted provider message IDs.
- Kept SMTP as default and retained SMTP for transactional password reset, verification and billing messages.
- Added Svix-verified, timestamp-bounded Resend webhook ingestion with provider-event deduplication. Delivered events update recipient delivery state; hard bounces and spam complaints create global suppression entries.
- Added campaign analytics details to the platform dashboard and migration `20261107_0050`.
- Verification: Python compilation, fresh SQLite migration through head, Alembic schema check and mocked Resend adapter success check passed. Pytest collection was blocked by missing `pyotp`; frontend dependencies/build and live Resend/webhook verification remain unavailable.
- Remaining: live provider/domain/webhook verification, complete webhook/API regression tests, close the provider-event/message-ID race, and add distributed worker claiming before multi-instance processing.


## Increment 52 — email worker coordination (2026-11-07)

Added a singleton database-backed lease for platform announcement campaign processing (migration `20261107_0051`). The worker atomically claims the lease, renews it between recipient sends, and releases it on exit; after a crash, the lease expires and a later scheduled run can resume queued/sending campaigns. The worker also reconciles Resend webhook events that arrived before the provider message ID was committed, including bounce/complaint suppression. Python compilation, fresh SQLite migration, downgrade/re-upgrade, Alembic drift check, empty-queue CLI smoke test, and SQLite lease contention/release smoke test passed. Live PostgreSQL multi-process contention, live Resend webhook race, full backend suite, frontend build, and production operation remain unverified. See `increment-52-email-worker-coordination-2026-11-07.md`.

## Increment 53 — Separate platform administrator demo access (2026-11-07)

- Added a dedicated administrator demo entry at `/admin/login`; when the backend has `DEMO_MODE=true`, it offers a one-click platform-owner demo session and redirects to `/platform`.
- Added `POST /api/v1/auth/demo-admin`, which issues a session only for the seeded, active, verified `DEMO_EMAIL` identity and only when `DEMO_MODE=true`.
- The demo identity receives owner-level platform permissions and a narrowly scoped MFA exception. The exception is checked server-side on every protected platform-admin API request and applies only to the configured demo identity while demo mode is enabled. Demo mode now also requires SQLite, preventing accidental use of shared PostgreSQL customer data.
- Production mode continues to reject `DEMO_MODE=true`; ordinary configured owners and delegated administrators retain the existing MFA requirement. Normal customer demo login remains unchanged at `/login`.
- Added backend regression coverage for demo owner access without MFA, endpoint denial outside demo mode, and rejection of ordinary customer accounts from platform administration.
- Verification status: source compilation and focused test outcomes are recorded in the Increment 53 implementation report. Live deployment and frontend production build are not implied by repository changes.


## Increment 54 — Demo separation audit and correction (2026-11-07)

- [x] Full source audit found that Increment 53 reused the customer demo identity as the platform-owner demo identity. This meant customer demo sessions inherited global administrator permissions.
- [x] Split demo seeding into `DEMO_EMAIL` (customer) and `DEMO_ADMIN_EMAIL` (platform owner), each with a separate user and workspace.
- [x] Removed the demo Docker image's `PLATFORM_ADMIN_EMAILS=admin@example.com` allowlist entry; the admin demo identity is recognized only by the narrow demo-mode helper.
- [x] Customer `/login` action is now labelled `Enter customer demo`; admin access remains at `/admin/login` and `/platform`.
- [x] Added regression coverage that the customer demo identity cannot call platform-admin APIs.
- [ ] Focused/full pytest, frontend build, browser testing, and live Render/Vercel demo validation remain blocked or pending; see Increment 54 audit report.
