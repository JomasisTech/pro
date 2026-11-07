## 2026-11-05 — Increment 29: PostgreSQL test safety and frontend lockfile attempt
- Added a strict safety gate before destructive PostgreSQL integration tests: explicit opt-in, local test host, and a disposable database name (`ci_db` or `test_*`).
- Added three unit tests proving the safety gate rejects missing opt-in, production-like database names, and remote hosts. CI sets the opt-in only for its isolated PostgreSQL 16 service.
- Verification: all 51 backend test files in two groups — **364 passed, 3 skipped**; Python compileall passed; SQLite Alembic upgrade/downgrade/re-upgrade and `alembic check` passed with no schema drift. The 3 PostgreSQL-gated tests remain skipped locally.
- Attempted genuine `frontend/package-lock.json` generation with Node 22.16.0/npm 10.9.2. npm registry DNS failed (`EAI_AGAIN registry.npmjs.org`) and both bounded attempts timed out. No fabricated lockfile was added. Frontend dependency install/lint/typecheck/build/browser QA remain unverified.
- PostgreSQL 16 CI workflow was inspected but not executed from this environment; no claim of real PostgreSQL verification is made.
- Detailed evidence and next steps: [`increment-29-postgres-and-frontend-lockfile-2026-11-05.md`](increment-29-postgres-and-frontend-lockfile-2026-11-05.md).

# Completed Work

## Initial repository starter — 2026-11-02
Prepared a starter repository containing:
- FastAPI system endpoints
- SQLAlchemy database connection/session foundation
- Environment-driven settings
- Alembic setup for future schema migrations
- Basic endpoint tests
- Next.js placeholder landing page
- Dockerfile and Render deployment blueprint
- Project documentation

**Verification status:** Files have been generated, but tests and live deployment have not been run in the user's environment. This is a starter milestone, not a claim that Stage 1 is fully complete.

## 2026-11-02 — Initial identity data layer
- Added SQLAlchemy models for users, organizations, and organization memberships.
- Added a first Alembic migration for those three tables, including unique email/slug constraints and one membership per user/organization pair.
- Registered model metadata with Alembic.
- Added isolated model tests covering relationships and uniqueness constraints.
- Verification in this workspace: `pytest -q` reports 8 passed, 1 skipped. The migration was applied successfully to a temporary SQLite database as a cross-dialect smoke test.
- PostgreSQL is not yet live-verified in this environment: the PostgreSQL driver is declared in `pyproject.toml` but is not installed here, and no PostgreSQL server is available. Authentication endpoints are not implemented yet.

## 2026-11-02 — Login rate limiting and organization authorization
- Added `FailedAttemptLimiter` (`app/core/rate_limit.py`) and applied it to `POST /auth/login`.
- Added organization routes and the reusable `get_membership` / `require_roles` dependencies.
- Added tests: `test_rate_limit.py`, `test_organizations.py`, and lockout tests in `test_auth.py`.
- **Verification:** the three limiter unit tests were executed locally and passed. The API and organization tests were only syntax-checked because FastAPI/pytest could not be installed offline; they run for the first time in GitHub Actions.

## 2026-11-02 — Known-issue fixes (D-011)
- Dummy Argon2 verification for unknown emails (login timing).
- Proxy-aware client address (`app/core/network.py`) and optional per-address login limiter.
- Production startup check for `SECRET_KEY`; `render.yaml` now generates one and lists the new proxy variables.
- `/ready` test no longer needs a live database.
- **Verification:** `test_network.py` (4 tests) executed locally and passed. Config, login, and health changes were only syntax-checked offline; they run first in GitHub Actions.

## 2026-11-02 — Dashboard workspace integration (Stage D, first slice)
- `fetchMyOrganizations` and `saveActiveOrganization` in `frontend/src/lib/auth.ts`; dashboard header now uses real organization data with an accessible workspace dropdown.
- **Verification:** TypeScript syntax check only (no syntax errors). Dependencies could not be installed offline, so type-checking, lint, build, and browser behavior are unverified until the CI frontend job runs.

## 2026-11-02 — Create workspace (vertical slice)
- Backend: `POST /api/v1/organizations`, shared `build_organization_slug` helper (registration now uses it), request validation, per-user cap, 6 new tests.
- Frontend: `createOrganization` client and a "New workspace" form inside the workspace dropdown.
- **Verification:** Python files compile and the TypeScript passes a syntax check. The new tests and the UI have not been run (offline sandbox); first run happens in GitHub Actions.

## 2026-11-02 — Categories and business profile (vertical slice, continuation by a second AI session)
- Backend: `IndustryCategory` and `BusinessProfile` models, migration `20261102_0002` (tables plus starter category data), `GET /categories`, `GET/PUT /organizations/{id}/profile`, 11 new tests in `tests/test_profiles.py`.
- Frontend: `lib/profile.ts` client, `/onboarding` business-profile form, "Business Profile" dashboard nav link.
- **Verification:** all new Python files compile and the seed data was checked for unique slugs/ids. Dependencies could not be installed (no network), so the new tests, the migration, the TypeScript, and the UI have NOT been run. First run happens in GitHub Actions.

## 2026-11-02 — Onboarding redirect
- Dashboard sends owners/admins whose workspace has no business profile to `/onboarding` (once per session; "Skip for now" is remembered in `sessionStorage`). Creating a new workspace also opens onboarding. Saving the profile returns to the dashboard.
- **Verification:** none run (no Node dependencies offline); logic reviewed by reading only. Verify in a browser: new account -> onboarding; skip -> dashboard; save -> dashboard without redirect.

## 2026-11-02 — AI caption generation (backend slice)
- Added the AI provider interface + OpenAI HTTP client (`app/integrations/ai_provider.py`), brand-aware prompt builder (`app/modules/content/prompts.py`), and `POST /organizations/{id}/content/generate-caption` with profile requirement, hourly per-user limit, and safe error mapping. `httpx` moved to runtime dependencies.
- Tests: `test_ai_provider.py` (mocked HTTP) and `test_content.py` (fake provider).
- **Verification:** files compile only. No test was run and no real OpenAI call was made; the OpenAI request/response shape and default model name are unverified against current provider docs.

## 2026-11-02 — Central plans and usage limits
- `app/core/plans.py` is the single source of plan limits (free/standard/premium, placeholder numbers). `organizations.plan` column, `usage_events` table (migration `20261102_0003`), `require_quota` dependency + `record_usage`, `GET /organizations/{id}/usage`. AI caption generation now enforces the monthly plan quota (402). Docs: `docs/plans-and-limits.md`.
- Tests: `tests/test_plans.py` (incl. a test proving a one-number catalog change alters enforcement); one existing hourly-limit test now uses the premium plan.
- **Verification:** files compile only; nothing run.

## 2026-11-02 — Drafts and Content page (vertical slice)
- Backend: `content_drafts` table (migration `20261102_0004`), `GET/POST/PATCH/DELETE /organizations/{id}/drafts`, owner/admin-only approve/reject, tenant scoping, 8 tests in `tests/test_drafts.py`.
- Frontend: `lib/content.ts`, `/content` page (generate, edit, save draft, list, approve/reject, delete, usage line), sidebar "Social Media" now opens it.
- **Verification:** Python compiles; nothing executed (no dependencies offline). TypeScript and UI unchecked.

## 2026-11-02 — Organization activity log
- `activity_logs` table (migration `20261102_0005`), `record_activity` helper, hooks in drafts, business profile, and workspace creation, read-only `GET /organizations/{id}/activity` (owners/admins), `/activity` page + sidebar link, 9 tests in `tests/test_activity.py`, docs in `docs/activity-log.md`.
- **Verification:** Python compiles only; nothing executed. TypeScript and UI unchecked.

## 2026-11-02 — First executable backend test pass (continuation)
- Inspected the project handoff records and resumed from the documented next step: verify the current implementation before adding another feature.
- Fixed a test collection error in `backend/tests/test_content.py`: the `sessionmaker` type annotation was used but not imported.
- **Verification:** with a SQLite test database and test-only `SECRET_KEY`, `pytest -q` reports **100 passed, 1 skipped**. `python -m compileall -q app tests` also passed.
- **Limitations:** this runtime is Python 3.13, while the project targets Python 3.12. The skipped test is PostgreSQL-specific; no live PostgreSQL migration verification was possible. Frontend `npm install` did not complete before timeout, so lint/build/browser checks remain unverified. GitHub Actions has not been run from this archive.

## 2026-11-02 — Expanded business onboarding and shared context

- Added nullable, backward-compatible business profile fields for niche, audience type, geographic market, unique selling points, preferred tone, preferred phrases, and avoided phrases.
- Added Alembic migration `20261102_0006_business_onboarding_context.py`.
- Expanded the `/onboarding` form; new submissions require an industry and an explicit free-text niche, while social account connection remains optional.
- Added tenant-scoped `GET /api/v1/organizations/{organization_id}/business-context`, including completeness and missing core fields, and marked its data provenance as `user_provided`.
- Routed AI caption generation through the shared business-context service and included the additional niche/brand preference fields in prompts.
- Added backend tests for the new profile fields, context endpoint, tenant isolation, completeness, and prompt usage.
- Verification: **104 passed, 1 skipped** in SQLite tests; Python compileall passed; SQLite Alembic upgrade reached `20261102_0006`; `alembic check` reported no new upgrade operations. PostgreSQL and frontend lint/build/browser verification remain outstanding.


## 2026-11-02 — Structured products, profile review, and version history
- Added organization-scoped structured product/service CRUD, optional price/currency, primary-product selection, active state, and tenant ownership checks.
- Added profile confirmation endpoint with required-field checks, `confirmed_at`, and first `onboarding_completed_at` timestamps. Any subsequent profile edit clears confirmation.
- Added immutable JSON snapshots for profile create/update/confirm actions and a member-readable history endpoint.
- Extended shared business context to include active structured products and to count them toward products/services completeness.
- Added Alembic migration `20261102_0007_profile_review_and_products.py`.
- Verification in the authoring environment: **109 passed, 1 skipped** using SQLite test databases. PostgreSQL and frontend build/browser checks remain outstanding.

## 2026-11-02 — Frontend business profile workflow
- Added frontend API client functions for structured products/services, profile confirmation, and profile history.
- Added `/products` with create, edit, archive/restore, and delete actions; currency and optional price are supported.
- Added `/profile` review page with category/subcategory labels, explicit confirmation, confirmation state, and recent version history.
- Updated onboarding save flow to continue to profile review and added dashboard navigation links for Business Profile and Products & Services.
- Hardened the backend product PATCH schema so an explicit null product name is rejected as a validation error instead of reaching the database.
- Verification: backend **109 passed, 1 skipped**, Python compileall passed, SQLite Alembic upgrade through `20261102_0007` passed, and `alembic check` reported no new operations. Frontend lint/build could not run because frontend dependencies are not installed; `npm ci` cannot run without a lockfile and `npm install` timed out. Global TypeScript check was attempted but is not meaningful without Next.js/React type packages. Browser QA remains outstanding.

## Social account foundation — 2026-11-02
- Added organization-scoped social account metadata model and Alembic migration `20261102_0008`.
- Added provider registry, connected-account inventory, and owner/admin disconnect APIs.
- Added `/social-accounts` frontend screen and dashboard navigation.
- Added tenant isolation and disconnect authorization tests.
- Verification: 111 passed, 1 skipped; Python compileall passed; SQLite migrations through 0008 passed; Alembic reports no pending model changes.
- OAuth, credentials, token encryption/refresh, provider API access, post sync and brand analysis remain future work. Frontend build/browser tests remain unverified because frontend dependencies are not installed in this environment.

## 2026-11-02 — Meta Instagram Login foundation

- Added one-time, expiring, tenant/user-bound OAuth state records and a Meta Instagram Login authorization/callback flow.
- Added encrypted-at-rest social credential storage using a dedicated Fernet key; browser APIs never expose token values.
- Added provider readiness gating, Instagram Connect UI, OAuth result page, environment template, migration `20261102_0009`, and mocked OAuth tests.
- Verified: backend tests **113 passed, 1 skipped**; live Meta authorization is not tested (credentials and public callback unavailable); Facebook Page OAuth remains separate and unimplemented.


## 2026-11-02 — Video Content Studio foundation
- Added the AI video-script API for TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, and long-form YouTube, with selectable duration, creative style, and optional CTA.
- Prompt produces a hook, timestamped scene plan, visuals, on-screen text, spoken dialogue/voiceover, caption, platform title, description, hashtags, and recording notes. It explicitly forbids fabricated prices, product claims, results, or testimonials.
- Added separate `ai_video_scripts` monthly plan limits and hourly abuse protection.
- Updated the Content Studio UI with Caption and Video Script modes; generated scripts can be edited and saved as drafts up to 12,000 characters.
- Added YouTube to the social-provider registry. TikTok and YouTube connection/publishing remain unavailable until OAuth and official upload flows are implemented.
- Verification: **115 passed, 1 skipped** in SQLite tests. Frontend build/browser validation remains unverified because dependencies are not installed.


## TikTok Login Kit OAuth foundation
- Added TikTok web OAuth start/callback using official Login Kit endpoints.
- Bound one-time OAuth state to organization and user; persisted only its SHA-256 hash.
- Exchanged authorization code server-side, fetched TikTok display identity, and encrypted access/refresh tokens.
- Enabled TikTok Connect in the UI only when required server configuration is present.
- Direct video publishing remains pending TikTok app approval/audit and the Content Posting API upload/status workflow.

## TikTok Content Posting API foundation

- Added creator-info retrieval, Direct Post initialization using TikTok `FILE_UPLOAD`, explicit consent, current privacy/interactions validation, duration enforcement, and provider status fetch.
- Added durable `tiktok_publish_jobs` records and migration `20261102_0010`.
- Added a TikTok publishing page that uploads video chunks directly from the browser to TikTok and lets the user refresh publish status.
- Private-only guard remains enabled by default until TikTok audit approval (`TIKTOK_CONTENT_POSTING_AUDITED=false`).
- Backend test suite: 119 passed, 1 skipped. Live provider flow and frontend build remain unverified.


## TikTok token refresh and YouTube OAuth foundation
- Added server-side TikTok access-token refresh before expiry, including refresh-token rotation when returned by TikTok. Tokens remain encrypted at rest and are never sent to the browser.
- Added Google OAuth for YouTube using a one-time hashed state, offline access, OpenID identity, and the `youtube.upload` scope. Access and refresh tokens are encrypted in the existing social credential store.
- Enabled YouTube Connect only when the required Google OAuth and encryption settings are configured.
- Added automatic TikTok publishing-status checks in the publishing page while a post is processing.
- YouTube channel selection/verification, resumable media upload, processing status, TikTok upload-session recovery, and live provider tests remain future work.


## YouTube resumable upload foundation — 2026-11-02
- Added a durable YouTube publishing job model and Alembic migration `20261102_0011`; the resumable session URL is encrypted at rest.
- Added API routes to initialize `videos.insert` resumable sessions, verify uploaded video IDs against the connected channel, and query `status` / `processingDetails`.
- Added browser upload using 8 MiB chunks, `308 Resume Incomplete` handling, and retry probes after transient network failures. OAuth tokens remain server-side.
- Added `/youtube-publish` UI for channel, video metadata, privacy, made-for-kids declaration, explicit consent, upload progress and processing status.
- Verification: 124 passed, 1 skipped; compileall and SQLite migration/alembic check passed. Frontend build, Google live API, PostgreSQL, and browser CORS behavior remain unverified.

## Facebook Pages and calendar milestone
- Added separate Facebook Login OAuth with one-time state and Page discovery; Page access tokens are encrypted server-side.
- Added Facebook text/link Page publishing and Meta-native scheduled posts.
- Added a provider-backed calendar-entry table and `/calendar` feed combining saved drafts with Facebook scheduled/published posts.
- Added `/facebook-publish` and `/calendar` frontend pages.
- Added migration `20261102_0013`.
- Facebook photo/video publishing, TikTok/YouTube calendar event aggregation, cross-platform background scheduling, and provider-side cancellation/rescheduling remain future work.

## 2026-11-02 — First stabilization and audit-remediation batch
- Added transactional audit events for structured product/service create, update, delete, and primary-offer changes; social account disconnect; provider OAuth connection callbacks; and Facebook/TikTok/YouTube publishing job lifecycle changes.
- Corrected Facebook calendar date filtering so immediate posts with no `scheduled_at` are found using `created_at`.
- Added cursor pagination to Facebook Page discovery and prevented a false `connected` result when no discovered Page has `CREATE_CONTENT`.
- Replaced dashboard sample metrics and fabricated connected-account cards with organization-scoped draft and social-account data from the API. Removed navigation to future products and connected active dashboard actions to implemented routes.
- Corrected calendar timestamp labels, added editable product currency selection, and clarified that YouTube authorization currently selects the Google identity rather than offering explicit multi-channel selection.
- Reconciled current project status and provider/activity-log documentation with the implementation.
- Verification: **129 passed, 1 skipped** on SQLite; Python compileall passed; SQLite Alembic upgrade through `20261102_0013` and `alembic check` passed; TypeScript/TSX syntax transpilation passed for 21 files.
- Still unverified: PostgreSQL 16, npm dependency installation, frontend ESLint/production build, browser end-to-end flows, live provider OAuth/publishing, GitHub Actions and deployment.


## 2026-11-02 — Calendar interface
- Added responsive month, week, and 30-day agenda views over the existing calendar endpoint.
- Added previous/next navigation, Today shortcut, day-to-agenda drill-down, and daily event previews.
- Kept provider coverage limitations visible: the feed still contains drafts and Facebook Page entries only.
- Frontend lint/build/browser verification remains outstanding because dependencies are unavailable in the authoring runtime.

## Durable scheduling — first provider adapter
- Added provider-neutral scheduled-post records and migration `20261102_0014`.
- Added tenant-scoped schedule create/list/cancel/reschedule endpoints, owner/admin lifecycle permissions, activity logging, and scheduled-post quota enforcement.
- Added an atomic-claim database dispatcher with bounded retries and a Facebook Page text/link publishing adapter. Run it periodically using `python -m app.modules.posting.dispatcher`.
- Added calendar feed visibility and a connected-Facebook-Page scheduling form.
- Verification: **133 passed, 1 skipped** using SQLite; Python compileall passed; SQLite migration upgrade through `20261102_0014` and Alembic metadata check passed.
- Not yet verified: PostgreSQL, live Meta API behavior, frontend dependency installation/lint/build, browser workflow, and deployment of a recurring dispatcher process.

## Authentication: logout, change password, password reset (2026-11-04)
- Backend endpoints `logout`, `logout-all`, `change-password`, `forgot-password`, `reset-password`; migration `20261104_0020`; `RevokedToken` and `PasswordResetToken` models; SMTP email helper; settings for reset TTL, limits, SMTP and frontend URL.
- Frontend sign-out revokes the server token; `/forgot-password`, `/reset-password`, `/security` pages.
- Added `backend/tests/test_auth_sessions.py` (18 tests). Not run in the authoring environment (no network to install dependencies); run `pytest` before merging.
- Auth pages (login, register, forgot/reset) use one blue accent (--auth-accent) and a single blue focus ring; removed the '8+ characters' hint from login.
- Form-field focus is now one global blue style (globals.css) for every input/select/textarea in the app; purple focus classes removed from content, products and onboarding.

## Phase 1 completion pass (2026-11-04)
- Workspace rename/delete + `/workspace` page; `PATCH /auth/me` + account name form; draft paging and author-only member deletes; activity-log filters; configurable workspace cap; `.env.example` files.
- Added `backend/tests/test_phase1_completion.py` (9 tests). Not run in the authoring environment (no network to install dependencies).


## 2026-11-04 — Bounded local failed-attempt limiter
- Fixed a memory-growth edge case: when the local limiter reached its 10,000-key cap and all keys were still active, new distinct keys could still be added without bound. It now prunes expired keys (at most once per second) and evicts the least-recently-active key that is not blocked before admitting a new key at capacity.
- Follow-up fix (same day): the first version evicted the oldest key even when it was blocked, so flooding the limiter with distinct keys could erase an active lockout. Blocked keys are now never evicted, and when the table is full of blocked keys the limiter fails closed instead of admitting new keys.
- Second follow-up: eviction is now tiered (fewest failures first, then least recent, in batches of 10% of capacity) so a flood of single-failure keys cannot reset a key with more failures, and when the table is full of blocked keys new keys share a bounded overflow budget instead of being rejected outright, so legitimate users are not locked out during a flood while attacker guesses stay capped.
- Replaced the single eviction test with new limiter tests: oldest-unblocked eviction, flood cannot clear an active block, recent activity protects a key, high failure count survives a low-count flood, shared overflow budget, and recovery after expiry/reset. Verified by running the rate-limit tests with a minimal pytest shim (9 of 9 passed in this environment, where pytest and the backend dependencies are not installed); the full suite was not run.
- Verification limitation: pytest could not collect because this runtime lacks the backend `psycopg` dependency; `npm install --package-lock-only` timed out, so frontend lockfile/build work could not be completed. These are not reported as passing checks.

## 2026-11-04 — Facebook scheduler uncertain-outcome regression tests
- Added parameterized regression coverage for a Facebook publish POST that ends in a network read timeout or HTTP 503 after submission.
- Confirms the dispatcher marks the job failed, clears the retry timestamp, and persists an explicit uncertain-outcome warning instead of automatically retrying a potentially accepted post.
- Verification (recorded by the earlier authoring run): focused scheduler regression plus rate-limiter tests **6 passed**; full scheduling test module **12 passed**; Python compileall passed. Full backend suite exceeded the runtime limit before completion. PostgreSQL and live Meta publishing were not tested.

## 2026-11-04 — Instagram scheduler ambiguity regression tests
- Added `test_dispatcher_does_not_retry_ambiguous_instagram_media_publish_failure` (timeout and 503 at `media_publish`, after the container was created): job is marked failed with an uncertain-outcome message, `next_attempt_at` stays empty, no external post ID is stored, and a later dispatch two hours on does not retry.
- Added `test_dispatcher_retries_instagram_failures_that_cannot_have_published` (timeout or 503 while creating the container, and a 400 rejection at `media_publish`): job is re-queued with the normal 60-second backoff, and `media_publish` is never called when no container exists.
- Shared helpers `_seed_due_instagram_job` and `_install_failing_instagram_client` keep the cases short.
- Verification: the file compiles (`py_compile`) and has no duplicate test names. These new tests were **not executed**: the authoring environment has no network and lacks `sqlalchemy`, `httpx`, `fastapi` and `pytest`. Run `pytest backend/tests/test_scheduling.py` before relying on them.

## 2026-11-04 — Code review fixes (media, scheduling)
- **Signed media URLs:** `GET /media-assets/{id}/file` called `hmac.compare_digest` on the raw `signature` string; a signature containing non-ASCII characters raised `TypeError` and returned a 500 to an unauthenticated caller. Comparison is now done on bytes via `_signature_matches`, so such input gets the normal 403.
- **Uploaded filenames:** the browser sends `X-File-Name` percent-encoded (`encodeURIComponent`), but the API stored it as received (e.g. `My%20Video.mp4`). It is now decoded and sanitised by `_clean_filename` (path parts and control characters removed, 255-character cap).
- **Cancel/reschedule race:** both endpoints checked `status == "queued"` and then wrote unconditionally, so a worker claiming the post in between could be overwritten (a post could go out after being cancelled and end up recorded as cancelled). Both now use a compare-and-set `UPDATE ... WHERE status = 'queued'` and answer 409 if the worker won.
- **Scheduled-post responses:** list/create/reschedule previously returned the raw database row, including `lease_token`, `lease_expires_at`, `processing_started_at` and `provider_publish_id`. A `ScheduledPostResponse` model now omits those worker internals; all other fields the frontend uses are unchanged.
- **Approved content is what is stored:** the schedule stored the request's `content` (only compared after `strip()`), so stray whitespace could differ from the approved draft. It now stores `draft.content`.
- Added tests for each (`test_media_assets.py`: 2; `test_scheduling.py`: 3 including a parametrized race test). Verification: files compile, and the signature/filename helper logic was exercised standalone (13 checks passed, and the old `TypeError` was reproduced). The API-level tests were **not executed** (no `fastapi`, `sqlalchemy`, `httpx` or `pytest` here); run `pytest backend/tests` before relying on them.


## 2026-11-04 — Increment 15: scheduled payment reconciliation
- Added bounded pending-payment reconciliation with a 10-minute default age threshold, direct Paystack verification, provider-neutral registry use, and reuse of idempotent subscription fulfillment.
- Added `POST /api/v1/platform-admin/billing/reconciliation/run`, platform audit logging, and a **Run reconciliation** action on `/platform`.
- Added `python -m app.jobs.reconcile_payments` as the scheduled-job entry point. Hosting cron must invoke it every 5–10 minutes; FastAPI does not start an in-process scheduler.
- Verification: focused tests **13 passed** (SQLite and mocked provider); Python compileall passed. Live Paystack, PostgreSQL concurrency, frontend build/browser QA, and deployed cron remain outstanding.

## 2026-11-04 — Increment 16: subscription lifecycle and customer billing
- Added owner-only cancellation-at-period-end and cancellation-resume endpoints, both tenant-scoped and activity-logged.
- Added safe, organization-scoped payment history to the customer billing API and `/billing` page, including pending, failed and paid attempts.
- Added subscription lifecycle processor and CLI: cancellation takes effect at the paid period boundary; subscriptions without verified renewal enter a configurable grace period and then expire/downgrade to Free.
- Added backend setting `BILLING_GRACE_PERIOD_DAYS` (default 3, allowed 0–14) and scheduled command `python -m app.jobs.process_subscription_lifecycle`.
- Successful verified payment fulfillment clears cancellation and grace state; renewals remain customer-initiated (no recurring charge is performed).
- Extended platform admin customer/overview subscription visibility with past-due/cancelled/expired states and grace/cancellation timestamps.
- Added migration `20261104_0033`.
- Verification: focused billing, Paystack, platform-admin and lifecycle tests **41 passed** using SQLite/mocked Paystack; Python compileall passed; SQLite Alembic upgrade/downgrade/re-upgrade and `alembic check` passed. Frontend dependencies are absent, so frontend lint/typecheck/build/browser tests were not run. PostgreSQL 16 and live Paystack/Google Pay remain unverified.


## Increment 17 — Paystack recurring-charge adapter foundation (2026-11-04)

- Added `PaystackProvider.charge_authorization` for Paystack's recurring authorization debit endpoint.
- Validates server-selected positive amount, NGN/USD currency, authorization code prefix and reference format; authenticates with the server-only secret key; rejects a mismatched provider reference.
- Added mocked HTTP tests. Verification: 17 focused checkout/fulfillment/lifecycle/reconciliation tests passed; Python compile check passed. No migration required.
- Important boundary: this does not yet store card authorizations, obtain customer consent, run renewal jobs, or activate subscriptions from a recurring charge. These must be implemented before automatic billing is enabled.


## Increment 18 — recurring consent and encrypted authorization storage (2026-11-04)

- Added optional consent UI to prepare a reusable authorization for possible future renewals. The UI states automatic renewal is not active yet and that the customer will be notified before activation. Unchecked means one-time checkout only.
- Checkout API persists timestamp, consent version and server-authored consent snapshot with the payment attempt; browser cannot provide an authorization code or alter the amount.
- Successful server-side Paystack verification stores an authorization only when the payment has consent, Paystack reports `reusable: true`, the verified customer authorization code is present, and the dedicated billing Fernet key is configured.
- Added dedicated `BILLING_AUTHORIZATION_ENCRYPTION_KEY`; never reuse the social OAuth encryption key. Exact original checkout email is retained. Only last4/type/expiry metadata is stored; no PAN/CVV.
- Added migration `20261104_0034` for payment consent evidence and encrypted subscription authorization metadata.
- Focused test command: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_billing_checkout_fulfillment.py tests/test_paystack_checkout.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py` — **20 passed**.
- Automatic renewals remain disabled; Increment 18 is secure consent/credential preparation, not a recurring billing scheduler or charging workflow.


## Increment 20 — platform-admin top customer leaderboard (2026-11-04)

- Added `GET /api/v1/platform-admin/top-customers?currency=NGN|USD&sort=desc|asc&limit=10`, protected by the existing verified platform-owner guard.
- The metric is lifetime sum of `payment_transactions.amount_minor` for `status=paid`, grouped by `initiated_by_user_id`. Pending, failed, unverified and deleted-user/unattributed transactions are excluded. Response includes rank, customer identity/status, currency, successful-payment count and latest paid timestamp.
- The `/platform` dashboard now displays the top 10 with rank 1 through 10, total spend, payment count and account status. Admins can switch between highest-spend-first and lowest-spend-first and select NGN or USD.
- NGN and USD are intentionally ranked separately; the platform has no trusted FX conversion source, so unlike currencies are never added or directly compared.
- No database migration required.
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_platform_admin.py` — **8 passed**. The tests cover top-10 truncation, both sort directions, pending exclusion, currency separation, and non-admin denial.
- Frontend dependencies are absent; TypeScript/ESLint/Next build and browser/mobile QA were not run. PostgreSQL 16 query behavior and production deployment were not tested.


## Increment 22 — Paystack renewal customer authentication (2026-11-04)

- Added migration `20261104_0036_renewal_customer_authentication.py` with a nullable hosted `authorization_url` on each durable renewal attempt.
- The renewal worker now passes a return URL to Paystack and recognizes the documented `paused` / `authorization_url` response shape. It stores the hosted URL only when it is HTTPS on the exact `checkout.paystack.com` hostname; arbitrary provider-returned URLs are never exposed to customers.
- Added tenant-scoped `GET /api/v1/billing/organizations/{organization_id}/renewal-actions`. Workspace members can see that authentication is required, while only owners/admins receive the hosted authentication URL.
- Added owner/admin `POST /api/v1/billing/organizations/{organization_id}/renewal-actions/{reference}/verify`. It re-verifies the payment server-to-server, then uses the existing atomic fulfillment service. Pending verification leaves the attempt actionable; a provider-declined result marks the attempt failed. The hosted URL is cleared after successful verification.
- Updated `/billing` with a Payment authentication required panel, a Paystack authentication link, a Verify payment control, and automatic verification when Paystack returns to `?renewal_reference=...`. It reloads subscription/payment state after verification.
- Added tests for paused challenge persistence, callback URL construction, untrusted-host rejection, customer action visibility and return verification.
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_paystack_checkout.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py tests/test_platform_admin.py` — **39 passed**. `python -m compileall -q backend/app backend/tests` passed.
- Migration `20261104_0036` upgrade, downgrade to `20261104_0035`, re-upgrade and `alembic check` passed on file-backed SQLite; no model/schema drift. ZIP integrity passed.
- Frontend build/browser/mobile QA not run because `frontend/node_modules` is absent. PostgreSQL 16, live Paystack test mode, actual issuer OTP/3DS and deployed callback routing were not tested.

### Safety boundary

`BILLING_RENEWALS_ENABLED` remains `false`. Increment 22 makes an action-required renewal completable, but does not implement renewal emails, safe bounded retries for declined payments, operational alerting, live provider acceptance testing or production scheduler supervision. Do not enable unattended renewals yet.


## Increment 23 — durable billing notifications and pre-charge notice gate (2026-11-04)

- Added the billing notification outbox (`BillingNotification`) with a unique event key, delivery states, SMTP retry metadata and tenant/subscription/renewal-attempt references.
- Added migration `20261104_0037_billing_notification_outbox.py` and migration `20261104_0038_recurring_billing_notice_gate.py`.
- Added a one-time automatic-renewal activation notice, default three-day advance reminders, Paystack action-required notices and confirmed-decline notices.
- Added `python -m app.jobs.process_billing_notifications` to enqueue and deliver bounded batches. SMTP retries are bounded to five attempts with backoff; stale sending claims can be recovered after 20 minutes.
- Automatic renewal is blocked for each subscription until its activation notice is successfully handed to SMTP. Settings validation also requires the notification feature flag and SMTP host before `BILLING_RENEWALS_ENABLED` can be true.
- Tests: 57 passed in the focused billing/configuration suite; compileall passed; file-backed SQLite migration upgrade/downgrade/re-upgrade and `alembic check` passed.
- Limitations: actual SMTP, PostgreSQL 16, live Paystack, frontend/browser and deployment scheduler checks remain outstanding. This was a backend-only increment.


## Increment 24 — verification-only recovery for interrupted renewals (2026-11-04)

- Added `backend/app/modules/billing/renewal_reconciliation.py` and CLI `python -m app.jobs.reconcile_subscription_renewals`. It scans a bounded batch of `verification_pending` attempts and stale `processing` attempts older than ten minutes.
- A stale `processing` attempt is first moved to `verification_pending`, then reconciled using the existing durable Paystack payment reference and server-side `verify_and_activate` service. The job never calls `charge_authorization` and cannot create a second debit.
- Verified success marks the renewal attempt paid only after the existing amount/currency/reference/email checks and subscription fulfillment succeed. A provider-confirmed decline marks the attempt failed, applies the existing past-due/grace policy, and queues the idempotent failure email. Provider outages and mismatches remain pending/attention-required; no blind retry is performed.
- The job is deliberately independent of `BILLING_RENEWALS_ENABLED` because it only verifies already-created references and never initiates a payment. It can be scheduled every 5–10 minutes.
- No database migration or frontend change was required.
- Verification from `backend/`: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_billing_notifications.py tests/test_payment_reconciliation.py tests/test_subscription_lifecycle.py tests/test_billing_checkout_fulfillment.py tests/test_paystack_checkout.py` — **42 passed in 4.73s**. `python -m compileall -q app tests migrations` passed. File-backed SQLite Alembic upgrade head, downgrade to `20261104_0038`, re-upgrade head and `alembic check` passed with no schema drift.
- Not verified: PostgreSQL 16 row-lock/concurrency behavior, live Paystack verification responses, scheduler supervision, SMTP delivery, frontend build/browser QA and production deployment.


## Increment 25 — provider-directed retry and operations runner (2026-11-05)

- Added migration `20261104_0039_provider_directed_renewal_retry.py` with `subscription_renewal_attempts.retry_at`, `retry_count`, and `previous_reference`, plus a status/retry-time index.
- `PaystackProvider.charge_authorization` now parses provider error envelopes and raises `PaystackRetryWindowError` only when Paystack explicitly reports its recurring-card regulator delay (`retry_by` with timezone or “Charge attempt cannot be fulfilled until X minutes”). Other HTTP failures remain ordinary errors.
- `process_due_subscription_renewals` stores the provider-directed retry time only if it is future and no more than 24 hours away. `process_provider_directed_renewal_retries` performs at most one retry, only after the provider-specified time, only while consent/authorization/period eligibility remains valid, and generates a fresh Paystack reference for the retry while preserving the rejected reference in `previous_reference`. A second regulator rejection ends the retry path.
- Ambiguous network errors remain `verification_pending` and go through server-side verification; customer OTP/3DS challenges and generic declines are never automatically retried.
- Added `backend/app/jobs/run_billing_maintenance.py` to orchestrate notification enqueue/delivery, verification reconciliation, provider-directed retries, guarded due renewals, and lifecycle transitions. It emits structured JSON summaries and returns non-zero on infrastructure errors.
- Added a Render cron service in `backend/render.yaml`, scheduled every five minutes, with billing flags explicitly false. Added operations runbook `docs/operations/billing-scheduler.md`.
- Added `backend/app/jobs/check_billing_readiness.py` for DB connectivity and an optional one-off SMTP test to an explicitly supplied controlled inbox. Added mocked SMTP transport coverage.
- Added a PostgreSQL-gated integration test for the unique one-renewal-attempt-per-subscription-period constraint; it is wired into the existing PostgreSQL 16 CI service and was skipped locally because no `TEST_POSTGRES_URL` was supplied.
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_paystack_checkout.py tests/test_billing_notifications.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py tests/test_billing_checkout_fulfillment.py tests/test_platform_admin.py tests/test_config.py tests/test_production_config.py tests/test_postgres_connection.py tests/test_postgres_integration.py` — **65 passed, 3 skipped in 7.85s**; `python -m compileall -q app tests migrations` — passed; SQLite migration upgrade, downgrade to `20261104_0038`, re-upgrade and `alembic check` — passed.
- Still unverified: real SMTP inbox delivery, live Paystack test-mode regulator response, PostgreSQL 16 concurrency, Render deployment/cron alerts, frontend install/build/browser/mobile QA.


## 2026-11-05 — Increment 26: Product 01 stabilisation and verification audit

- Inspected the Increment 25 repository against `AGENTS.md`, the master development prompt, project status, known issues, and the Product 01 scope. Confirmed `docs/full-project-blueprint.md` is already included; no duplicate was added.
- Python compilation passed. All 51 backend test files were executed in two bounded partitions: **361 passed, 3 skipped**. The three skipped tests require PostgreSQL.
- Verified SQLite migrations through `20261104_0039`, downgrade to `20261104_0038`, re-upgrade to head, and `alembic check` with no schema drift.
- Confirmed frontend install/build gate is still blocked: no `package-lock.json` or `node_modules`; offline npm lockfile generation could not reach the registry; lint/build commands report missing `eslint`/`next`.
- Added `increment-26-stabilisation-audit-2026-11-05.md` and reconciled current status/known-issue documentation.
- No application code, API behavior, database schema, or production settings were changed. PostgreSQL 16, frontend build/browser QA, live providers, SMTP and deployed scheduler remain outstanding.


## Increment 27 — frontend CI verification gate (2026-11-05)

- [x] Added an explicit `npm run typecheck` script (`tsc --noEmit`) to the frontend package scripts.
- [x] Added a dedicated TypeScript type-check step to the existing GitHub Actions frontend job, between ESLint and the Next.js production build.
- [x] Updated local setup guidance to list lint, type-check, and production-build commands and to warn that `npm ci` must not be used until a reviewed lockfile is committed.
- [x] Fixed two `Promise.all` result-destructuring defects in the billing and platform-admin pages that left `actions` and `topData` undefined.
- [ ] A committed `frontend/package-lock.json` is still outstanding. This execution environment has an empty npm cache and cannot resolve `registry.npmjs.org` (`EAI_AGAIN`), so generating a genuine dependency lockfile was not possible. No synthetic lockfile was created.
- [ ] Frontend dependency installation, ESLint, clean TypeScript, Next.js build, and browser/mobile QA remain unverified. A global TypeScript 5.8.3 invocation was attempted but cannot provide a valid project check without Next/React/Node type packages; it did not report any remaining TS2304 undefined-name diagnostics after the two fixes. The CI workflow was updated but not executed from this environment; no GitHub Actions run result is available.
- [x] Static validation: `frontend/package.json` parsed as JSON; source import scan found only declared runtime/dev packages (`next`, `react`, `@eslint/eslintrc`) plus local and Node built-in imports.

**Outcome:** This increment strengthens the automated frontend gate but does not close the frontend build/reproducibility blocker. Next step is to generate and review `package-lock.json` in a network-enabled Node 22/npm 10 environment, then run clean install, lint, type-check, and production build.


## Increment 28 — Future lead-generation and live pipeline UX requirements (2026-11-05)

- [x] Captured the Product 02 AI-assisted lead-generation pipeline and customer workflow.
- [x] Captured Product 06 compliant data-source strategy, provenance, and collection controls.
- [x] Captured Product 04 AI outreach drafting/review, customer approval, suppression, unsubscribe, and delivery safeguards.
- [x] Added a shared architecture requirement for durable background-job progress and frontend stage-by-stage feedback.
- [x] Recorded that one AI provider can serve multiple structured tasks; separate models are optional and must justify their cost/quality benefit.
- [x] Updated AGENTS.md, development rules, master development prompt, project status, and decisions log.
- [x] Confirmed this is documentation/requirements capture only: no application code, migrations, provider integrations, or frontend screens were implemented.
- [ ] Product 01 and foundation hardening remain active. These future products must not be implemented until the owner changes project scope and the current stage is ready.
