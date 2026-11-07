## Latest handover — Increment 31 (2026-11-07)

- **Baseline:** `autobizpro-dashboard-profile-polish-final.zip` supplied in the current conversation.
- **Changes:** existing workspace profile now stores an explicit AI brand voice mode and owner instructions; generation uses only the latest approved social-derived analysis when the mode permits it; `/profile` links to existing workspace management areas; platform administrators can initiate audited password recovery to a customer's already-verified email. Migration: `20261107_0042`.
- **Verification:** focused backend tests **43 passed** with SQLite and a temporary external `pyotp` import stub because `pyotp`/`psycopg` are missing from this environment; Python compilation passed; fresh SQLite Alembic upgrade and `alembic check` passed. This is not a full dependency-complete or PostgreSQL test run. Frontend dependencies are absent; frontend lint/typecheck/Vitest/build/browser QA and SMTP delivery remain unverified.
- **Next:** read `increment-31-owner-profile-ai-voice-and-account-recovery-2026-11-07.md`; complete optional personal phone verification and lost-email support workflow only with appropriate verification safeguards; add AI voice preview/reset-to-approved-suggestions UX; run complete backend and frontend validation in a fully provisioned environment.

## Latest handover — Increment 30 (2026-11-05)

- Baseline: Increment 29 ZIP. Added only the features a parallel build had that this repository lacked; see the "Current handover — Increment 30" section at the end of this file and `increment-30-merge-of-missing-features-2026-11-05.md`.
- **Not executed in the authoring environment:** the new API tests, migration `20261105_0040`, and any frontend toolchain step (no FastAPI/SQLAlchemy/pytest installed, no network). Only compile checks and pure-logic tests ran. Run the backend suite and `alembic upgrade head` / `alembic check` first.

## Latest handover — Increment 27 (2026-11-05)

- Baseline: Increment 26 ZIP.
- Changes: added `frontend` package script `typecheck: tsc --noEmit`; added a dedicated TypeScript type-check step to `.github/workflows/ci.yml`; fixed Promise.all result destructuring in billing (`actions`) and platform admin (`topData`); updated root README setup/verification instructions. No backend feature code or database schema changed.
- Verification: package JSON and CI YAML parse. Static review confirmed both Promise.all tuple counts match their result arrays. Global TypeScript 5.8.3 emitted missing Next/React/Node declaration diagnostics because dependencies are absent; no remaining TS2304 undefined-name diagnostics appeared after the two fixes. Attempted package-lock generation; npm registry DNS failed with `EAI_AGAIN`. No lockfile was created. Frontend install, ESLint, valid project typecheck, build, browser QA, and GitHub Actions execution remain unverified.
- Next: on a network-enabled Node 22/npm 10 machine, run `cd frontend && npm install --package-lock-only --ignore-scripts --no-audit --no-fund`; review and commit `package-lock.json`; then run `npm ci`, `npm run lint`, `npm run typecheck`, and `npm run build`. Once lockfile is committed, consider switching CI from `npm install` to `npm ci`.
- Never claim Increment 27 closes frontend verification; it only adds the explicit type-check gate to CI.

# BizPilot Pro — AI/developer handover

**Last updated:** 2026-11-07 (Increment 31)  
**Repository:** BizPilot Pro / Business Automation Platform  
**Architecture:** FastAPI + SQLAlchemy/Alembic modular monolith; Next.js 15 + React 19 + TypeScript frontend  
**Current product scope:** Shared platform foundation + Product 01 Social Media Automation. Products 02–07 remain future roadmap.

> Read this file together with `AGENTS.md`, `master-development-prompt.md`, `project-status.md`, `development-rules.md`, `known-issues.md`, `decisions-log.md`, and `docs/full-project-blueprint.md`. Inspect the actual repository and run tests before assuming any item below is still correct.

## 1. Current state at a glance

The repository contains a substantial Product 01 implementation: authentication and organization/workspace access, business onboarding/context, AI content generation and drafts, social OAuth/publishing integrations, scheduling/calendar foundations, media handling, usage quotas, activity logging, and Brand Intelligence with manual provider sync plus a job dashboard.

**This is not yet a verified production-ready SaaS release.** The latest focused backend tests pass on SQLite with mocked provider calls, but PostgreSQL 16, frontend install/build/browser QA, real provider integrations, and deployment/operations remain unverified. Do not infer production readiness from unit tests or SQLite.

Latest work in Increments 8–24 added Paystack signature and transaction verification, durable payment/subscription/webhook records, a provider-neutral adapter contract, Paystack hosted checkout, a managed NGN/USD price catalog, customer checkout, signed/idempotent webhook receipts, server-side verification and initial subscription activation, subscription lifecycle management, encrypted reusable authorization custody, an opt-in recurring renewal worker, a platform-admin top-10 customer spend leaderboard, Paystack customer-authentication handoff, a durable billing-email outbox with a pre-charge notice gate, and verification-only recovery for stale/incomplete renewal attempts. Checkout is available when Paystack public/secret credentials are configured, but live merchant testing and production hardening remain outstanding. PayPal and Flutterwave are future adapters; Google Pay is a Paystack Checkout channel. The 7-day Premium trial is not configured.

## 2. Implemented capabilities

### Platform foundation and access

- FastAPI application, settings/configuration, SQLAlchemy database setup, Alembic migrations, health/readiness endpoints, and API v1 router.
- Users, organizations, memberships, workspace membership/role authorization, and organization-scoped backend dependencies.
- Argon2id password hashing with legacy PBKDF2 verification/upgrade.
- Registration/login/current-user APIs, token revocation/logout capabilities, password reset/change-password foundations, email verification tokens, and optional verification enforcement.
- Google sign-in and WhatsApp one-time-code sign-in foundations.
- Organization invitations: secure random tokens stored as hashes, seven-day expiry, single-use acceptance, email match enforcement, role checks, acceptance UI, and invitation list/status/resend/revoke API and workspace UI (resend has a 60-second cooldown and replaces the earlier link; accepting an invitation verifies the invitee's email).
- Shared activity log with transactionally recorded events for several organization-owned mutations.

### Business onboarding and AI content

- Industry categories and organization business profiles.
- Expanded onboarding/context fields: niche, audience, market, USP, preferred tone/phrases, avoided phrases, products/services.
- Structured organization-owned products/services CRUD and primary product handling.
- Profile confirmation/version snapshots and a tenant-scoped business-context endpoint.
- AI caption generation through an AI provider abstraction.
- Video Script Generator for TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, and long-form YouTube; scripts can be edited/saved as drafts.
- Content drafts with edit/delete/approval actions and frontend pages.

### Social accounts, publishing, scheduling, media

- Official OAuth integration foundations for Instagram, Facebook Pages, TikTok, and YouTube; encrypted credentials and provider-specific scope/token handling.
- Facebook Page text/link publishing and scheduling capabilities.
- TikTok Direct Post workflow and YouTube resumable upload + processing polling foundations.
- Shared scheduled-post records/dispatcher, calendar aggregation/UI, and private media asset storage with signed delivery URLs.
- Provider capability limits exist: do not claim unsupported post types/platform scheduling are available. See `project-status.md` and `known-issues.md` for precise restrictions.

### Owner profile controls and account recovery (Increment 31)

- Workspace profile supports `automatic`, `manual`, and `hybrid` AI brand voice modes plus owner-defined `custom_ai_instructions`.
- Caption/video-script generation uses only the latest approved Brand Intelligence analysis when allowed by the selected mode; pending/rejected proposals are ignored.
- `/profile` provides navigation to the existing business editor, Brand Intelligence, social accounts, workspace, security and billing sections.
- Platform administrators can initiate a one-time password reset for an active non-admin customer only when an existing email address is verified. The action is audited; the customer chooses their own password. Admins cannot see/set passwords or bypass email verification.
- Details and verification boundaries: `docs/project-management/increment-31-owner-profile-ai-voice-and-account-recovery-2026-11-07.md`.

### Brand Intelligence

- Tenant-scoped social post observations, provenance, AI analysis/proposals, conflict/review workflow, and owner/admin approval/rejection UI.
- Manual latest-20 retrieval adapters for Instagram, Facebook Pages, TikTok, and YouTube, subject to granted scopes and external app approval.
- Optional rule-based analysis (`POST /brand-intelligence/analyze?method=rules`) that needs no AI key: count-backed observations, an evidence level, and profile conflicts, using the same pending/approve/reject review as the AI mode.
- Durable sync-job records/API/worker, bounded retries/stale recovery, and dashboard job history/polling/retry controls.
- Existing accounts may need reconnect/reauthorization to grant read scopes: TikTok `video.list`, YouTube `youtube.readonly`, plus provider-specific Meta permissions.

### Usage limits and billing groundwork

- Central placeholder plan catalog (`free`, `standard`, `premium`) in `backend/app/core/plans.py`.
- Organization plan field, monthly usage-event accounting, quota enforcement, and usage endpoint.
- `GET /api/v1/billing/plans` and `/api/v1/billing/readiness`; migration `20261104_0030` seeds approved Standard/Premium prices in NGN/USD for monthly and annual billing.
- Provider-neutral contract and registry: Paystack is initial; PayPal and Flutterwave are explicitly future integrations. Google Pay is a Paystack channel, not a separate provider.
- Customer billing page `/billing` and payment return page `/billing/return` are implemented. Owners/admins can initialize checkout through `POST /api/v1/billing/organizations/{organization_id}/checkout`; backend selects and snapshots the database price.
- Signed Paystack webhook: `POST /api/v1/billing/webhooks/paystack`; verifies raw-body signature, stores a deduplicated receipt and verifies `charge.success` directly with Paystack before activation.
- Authenticated browser-return verification: `POST /api/v1/billing/organizations/{organization_id}/transactions/{reference}/verify`.
- Verified payment activates the subscription and organization plan atomically and records activity. Current periods are paid one-time; automatic recurring billing is not implemented.
- Platform-owner price APIs: `GET /api/v1/billing/admin/prices` and `PUT /api/v1/billing/admin/prices`, protected by the verified-email `PLATFORM_ADMIN_EMAILS` allowlist; changes are append-only audited. A platform-admin price editor is available at `/platform/billing-prices`; the navigation link appears only after the authenticated admin-price API confirms access.
- Increment 8: `backend/app/integrations/payments/paystack.py` verifies modern timestamped `Paystack-Signature` (five-minute tolerance, multiple `v1` signatures) and legacy `x-paystack-signature` HMAC-SHA512 using raw bytes. It does not process events or activate plans.
- Detailed payment requirements: `docs/paystack-billing.md`.
- Increment 23 adds `BillingNotification` and migration `20261104_0037` for a durable transactional-email outbox, plus migration `20261104_0038` for `subscriptions.recurring_billing_notice_sent_at`. The CLI `python -m app.jobs.process_billing_notifications` queues one-time automatic-renewal activation notices, queues advance reminders, and sends pending notices.
- Automatic renewal processing now requires `recurring_billing_notice_sent_at` to be populated; that timestamp is written only after the activation notice is handed to SMTP successfully. `BILLING_RENEWALS_ENABLED=true` also requires `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=true` and `SMTP_HOST` at settings validation. Keep it false until live provider, database and scheduler checks are complete.
- Increment 24 adds `backend/app/modules/billing/renewal_reconciliation.py` and `python -m app.jobs.reconcile_subscription_renewals`. It reconciles existing renewal references only; it never calls `charge_authorization`. Stale `processing` attempts older than ten minutes are moved to verification-pending before server-side verification. Confirmed success is fulfilled; confirmed decline is marked failed and queues the failure notice; provider outage/mismatch stays pending for later verification or manual review.

## 3. Latest increments and exact verification

- Increment 12: added payment interval snapshots/migration `20261104_0031`, owner/admin checkout initialization from the server catalog, Paystack signed webhook receipt/idempotency, server-side verification, atomic subscription activation and activity logging, customer `/billing` and `/billing/return` pages, and Billing navigation (including mobile). Focused suite: **31 passed** using SQLite and mocked Paystack. Python compileall passed. Frontend dependencies absent; lint/typecheck/build/browser QA not run. Live Paystack/Google Pay and PostgreSQL 16 remain unverified. File-backed SQLite migration upgrade/downgrade/re-upgrade passed. Automatic recurring billing, cancellation, refunds/disputes and webhook stuck-event recovery remain outstanding.

- Increment 11: added provider-neutral checkout/verification/webhook contracts and provider factory/catalog; Paystack hosted-checkout adapter; database-backed NGN/USD Standard/Premium monthly/annual price catalog; platform-admin price update/read APIs and immutable change history. Seed prices: Standard ₦7,500/$9.99 monthly and ₦75,000/$99.90 annual; Premium ₦15,000/$19.99 monthly and ₦150,000/$199.90 annual. Platform admin emails are configured using `PLATFORM_ADMIN_EMAILS`. Focused billing/provider suite: **40 passed** with SQLite and mocked Paystack HTTP. Full Alembic migration upgrade, downgrade of `20261104_0030`, and re-upgrade passed on SQLite. PostgreSQL 16, live Paystack, actual Google Pay checkout, and frontend build/browser QA are not verified. A full backend pytest run printed through 100% but did not terminate within 240 seconds, so it is not recorded as a pass. Checkout/webhooks remain disabled; no subscription is activated by this increment.

- Increment 10: added `PaymentTransaction`, `Subscription`, and `PaymentWebhookEvent` models plus Alembic migration `20261104_0029`. Database uniqueness guards cover Paystack references, provider transaction IDs, one subscription per organization, and webhook event keys. Pending/inactive defaults prevent schema creation from granting paid access. Focused suite: **34 passed in 2.18s**; Python compileall passed; full SQLite migration upgrade through `20261104_0029` passed; `alembic check` found no pending changes. PostgreSQL 16 and live Paystack remain unverified. No checkout or webhook endpoint was added.

- Increment 9: added server-side Paystack transaction verification retrieval and trusted expected-value comparison helpers. Tests cover API authorization, URL encoding, malformed/unsuccessful provider responses, HTTP/network errors, successful matches, and status/reference/amount/currency/email mismatches. Paystack-focused suite: **30 passed in 3.00s** with mocked provider HTTP and SQLite test configuration; Python compilation passed. No live Paystack request or payment was performed.

- Increment 7: connected Brand Intelligence frontend to durable sync-job API; added job history/status, bounded polling, retry controls. Targeted Brand Intelligence/provider suite: **25 passed** with SQLite and mocked provider responses. Python compilation passed. Frontend dependencies were absent; npm install timed out, so TypeScript/ESLint/Next build and browser QA were not verified.
- Increment 8: added Paystack signature verification helper and tests. Command: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest tests/test_paystack_signatures.py tests/test_billing_readiness.py tests/test_plans.py -q` from `backend/` — **18 passed in 2.26s**. `python -m compileall -q app tests` passed.
- These tests do not verify a live Paystack webhook, a real Paystack transaction, PostgreSQL, or any production deployment.

## Increment 15 — scheduled payment reconciliation

- `backend/app/modules/billing/reconciliation.py` scans a bounded batch of Paystack payment attempts still pending after the configured age threshold (default 10 minutes). It calls Paystack verification and reuses `verify_and_activate`; it never trusts webhook/browser payloads.
- `POST /api/v1/platform-admin/billing/reconciliation/run` is platform-owner-only and audited. `/platform` has a **Run reconciliation** button with a confirmation and result summary.
- `backend/app/jobs/reconcile_payments.py` is the scheduler entry point: from `backend/`, run `python -m app.jobs.reconcile_payments`. Configure the hosting platform's scheduled job/cron to invoke every 5–10 minutes. There is deliberately no in-process FastAPI timer, avoiding duplicate timers across replicas.
- Providers without adapters (PayPal/Flutterwave) are skipped. Provider unavailability/mismatches are reported without activating subscriptions.
- Verification: focused suite **13 passed** (`test_payment_reconciliation.py`, `test_platform_admin.py`, `test_billing_checkout_fulfillment.py`) with SQLite/mocked Paystack; Python compileall passed. No migration was required.
- Outstanding: actual cron configuration, PostgreSQL concurrency/locking, live Paystack test-mode checkout/webhook/reconciliation, frontend production build and browser QA.

## 4. Outstanding work — priority order

### P0 — establish reliable verification baseline

1. Install frontend dependencies in a network-enabled environment and generate/commit a reproducible `package-lock.json` (or explicitly choose another lockfile strategy).
2. Run frontend ESLint, TypeScript checks, and `next build`; fix errors before claiming frontend readiness.
3. Run browser/mobile end-to-end flows for registration/login, email verification/reset, workspace switch/invitations, onboarding/profile confirmation, products/services, drafts, social connections, publishing, calendar, and Brand Intelligence.
4. Run Alembic migrations and backend integration tests against PostgreSQL 16; SQLite is not a substitute.
5. Re-run the full backend suite in the declared Python runtime and resolve existing failures/timeouts; capture exact results. Check CI execution rather than merely noting workflow files exist.

### P1 — Product 01 provider and worker hardening

1. Live-test each OAuth/publishing/sync flow with approved test apps/accounts and exact granted scopes (Meta, TikTok, Google/YouTube).
2. Ensure existing TikTok/YouTube accounts reauthorize for the new read scopes where needed.
3. Validate Brand Intelligence sync scheduling, retries, stale-job recovery, PostgreSQL concurrency, and shutdown/restart behavior. Current worker is in-process; decide whether a separately supervised worker is required for deployment.
4. Confirm unsupported providers/scopes are skipped safely by automatic scheduling and do not create recurring failure noise.
5. Verify media persistence/shared storage and provider scheduling limitations in the actual hosting environment.

### P1 — billing hardening (initial checkout/fulfillment is implemented)

Follow `docs/paystack-billing.md`. Remaining work: frontend browser QA; persistent-DB migration checks and PostgreSQL 16 integration; Paystack test-mode checkout/webhook/Google Pay validation; PostgreSQL reconciliation concurrency tests; automatic renewals, cancellation, refunds/disputes, grace periods and invoices; PayPal/Flutterwave adapters when approved; AI model/provider cost monitoring. Never activate a paid plan from an unverified browser redirect or webhook alone.

### P2 — production security/operations and UX gaps

- Replace remaining in-memory rate limiters (including login/AI paths where still in use) with shared Redis-backed enforcement; test concurrency, expiry, restart, and Redis outage behavior.
- Validate SMTP delivery for email verification, password reset, and invitations.
- Review refresh-token/session strategy and secure HttpOnly cookie option before broad commercial rollout.
- Complete member management UX (invitation list/resend/revoke now exists) and all frontend loading/error/empty states.
- Review activity-log coverage, retention/export/search needs, and add events for missing sensitive mutations.
- Verify backups, monitoring, secrets rotation, CORS, HTTPS media origin, deployment health/readiness, and rollback procedure.

## 5. Known limitations and do-not-claim list

- Initial commercial prices are configured in the database. Customer checkout and initial verified Paystack fulfillment exist, but have not been tested with live Paystack or PostgreSQL and are not production-ready.
- Automatic recurring renewals, cancellations, refunds/disputes, invoices/receipts and settlement reconciliation are not implemented. Pending-payment reconciliation is implemented as a scheduled CLI job and platform-admin action in Increment 15, but the hosting scheduler is not yet configured.
- No real Paystack/Meta/TikTok/Google/OpenAI/SMTP provider test has been established by the focused mocked test runs.
- PostgreSQL 16 and multi-replica worker behavior remain unverified.
- Frontend install/build/lint/TypeScript/browser QA remain outstanding because dependency installation did not complete in the authoring environment.
- Some provider capabilities are deliberately narrower than the UI roadmap; consult current API contract docs and known issues before promising functionality.
- Product 02–07 are not in active implementation scope.

## 6. Instructions for the next AI model/developer

1. Start with `AGENTS.md` and all project-management docs listed at the top of this file.
2. Inspect the current code, migrations, tests, and git/worktree state. Do not trust this handover blindly if newer commits/files exist.
3. Work in a small increment with a clear acceptance test. Preserve the modular monolith, organization isolation, server-side authorization, and activity-log transaction rule.
4. Do not invent plan prices, provider permissions, product capabilities, or test results.
5. Run relevant tests and report exact commands/results plus anything not run.
6. Update this handover, `project-status.md`, `known-issues.md`, and `decisions-log.md` whenever implementation/status/decisions change.
7. Deliver a complete repository ZIP when that is the requested workflow; exclude secrets, `.env`, caches, `node_modules`, `.next`, and `.git`.


## 7. Admin access clarification

- Workspace member administration is available at `/workspace`: owners/admins can invite members; owners can change roles and remove non-owner members. Workspace roles are tenant-scoped.
- Account security is available at `/security`; profile/account settings are under the existing profile/security pages.
- Platform-owner billing-price administration is available at `/platform/billing-prices`, protected by a verified email allowlist (`PLATFORM_ADMIN_EMAILS`).
- The platform-wide customer account console is available at `/platform` (Increment 13): platform owners can search/list customers, inspect linked organizations/subscriptions and recent transactions, and suspend/reactivate customer accounts. It is not a full organization-wide suspension, deletion, impersonation, or subscription-editing console.

## 8. Billing operational cautions

- Apply `alembic upgrade head`; Increment 12 adds migration `20261104_0031`.
- Configure `PAYSTACK_PUBLIC_KEY`, `PAYSTACK_SECRET_KEY`, `PAYSTACK_WEBHOOK_SECRET`, `PLATFORM_ADMIN_EMAILS`, and the existing `FRONTEND_BASE_URL`. Configure Paystack webhook to `/api/v1/billing/webhooks/paystack`.
- Test Paystack in test mode before production. Google Pay availability depends on Paystack merchant enablement and customer eligibility.
- Billing is currently one-time charge per period, not automatic recurring renewal. Manual webhook retry is available (Increment 14); pending-payment reconciliation is available as a CLI/scheduler job and admin action (Increment 15). Renewals, cancellation, refunds/disputes and settlement reconciliation remain to be built.

## 4. Platform administration — Increment 13 (2026-11-04)

- `/platform` is the platform-owner administration dashboard. It is visible in navigation only when the authenticated user can call the existing verified-email `PLATFORM_ADMIN_EMAILS`-protected price API; every new backend endpoint independently enforces the same platform-admin guard.
- Dashboard overview shows customer, active-account, organization, active-subscription, pending-payment and failed-webhook counts.
- Customer directory supports name/email search, active/suspended filtering, pagination, customer inspection, linked organizations, subscription snapshots, and recent transactions.
- Account suspension sets `users.is_active=false` and increments `token_version`, invalidating existing bearer tokens. Reactivation permits future sign-in. Self-suspension and suspension of another allowlisted platform admin are rejected.
- Global account actions are written to append-only `platform_admin_audits` (migration `20261104_0032`). This is separate from organization activity logs because the action is platform-wide and may not belong to one tenant.
- `/api/v1/platform-admin/billing-operations` and the dashboard show Paystack key presence, inferred key mode, webhook-secret presence, recent transactions and webhook outcomes without exposing credentials. Key-prefix mode is only a configuration hint; it does not prove provider connectivity.
- Focused platform-admin + billing regression tests: **13 passed** on SQLite with mocked provider behavior. Python compileall passed. Migration `20261104_0032` upgrade/downgrade/re-upgrade passed on file-backed SQLite.
- Still outstanding: PostgreSQL 16 verification; frontend dependency install, lint/typecheck/build and browser/mobile QA; live Paystack test-mode checkout/webhook/return testing; Google Pay device/wallet eligibility; automatic renewals/cancellation/refunds/disputes and settlement reconciliation; configure the Increment 15 pending-payment reconciliation job in the hosting scheduler; organization-level suspension and customer data deletion workflow.

### Platform admin configuration

Set `PLATFORM_ADMIN_EMAILS` on the backend to a comma-separated list of verified platform-owner email addresses. Never put this setting or payment secret keys in `NEXT_PUBLIC_*` variables. Apply database migrations with `alembic upgrade head` before deploying the increment.

## 9. Increment 14 — manual Paystack webhook recovery

- Platform owners can manually retry failed Paystack `charge.success` webhook receipts from the `/platform` payment operations panel.
- Backend endpoint: `POST /api/v1/platform-admin/webhooks/{event_id}/retry`.
- Failed receipts are retryable; a receipt left `processing` is retryable only after ten minutes based on its original receipt time. Recent in-flight receipts return HTTP 409. Non-Paystack, non-`charge.success`, or reference-less events cannot be used to activate a subscription.
- Every retry performs a fresh server-to-server Paystack transaction verification and reuses `verify_and_activate`; the event's stored digest/metadata is not treated as proof of payment. Fulfillment remains idempotent because already-paid transactions return without extending the subscription again.
- Recovery attempts are recorded in `platform_admin_audits`. Increment 14 introduced manual webhook recovery; Increment 15 subsequently added a scheduled pending-payment reconciliation CLI and platform-admin run action.
- Focused verification command from `backend/`: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_platform_admin.py tests/test_billing_checkout_fulfillment.py tests/test_billing_price_admin.py tests/test_billing_readiness.py tests/test_paystack_checkout.py tests/test_paystack_signatures.py tests/test_paystack_transactions.py` — **36 passed**. `python -m compileall -q backend/app backend/tests` passed.
- No migration was added. PostgreSQL 16, actual Paystack test-mode transactions/webhook delivery, frontend dependency installation/production build, and browser/mobile QA remain outstanding.


## Current handover — Increment 16 (2026-11-04)

### Implemented in Increment 16

- Owner-only cancellation scheduling at the end of the paid subscription period and owner-only cancellation reversal before the period end. Both operations are tenant-scoped and write organization activity-log records.
- Customer billing API now exposes a bounded (latest 50) organization-scoped payment history, including pending, failed and paid attempts without exposing provider payloads.
- Customer `/billing` UI now shows payment history, pending cancellation, grace-period status and owner cancellation/resume controls.
- Added lifecycle service `backend/app/modules/billing/lifecycle.py`. It processes subscriptions whose paid period has ended: a scheduled cancellation becomes `cancelled` and organization plan becomes `free`; otherwise an active subscription becomes `past_due` for the configured grace window; after grace expiry it becomes `expired` and organization plan becomes `free`.
- Added `BILLING_GRACE_PERIOD_DAYS` backend setting (default 3; range 0–14; 0 disables grace) and CLI `python -m app.jobs.process_subscription_lifecycle`. Schedule every 15–60 minutes using the hosting scheduler.
- Successful verified payment fulfillment clears cancellation/grace markers and can reactivate a past-due subscription. Renewal still requires a customer-initiated checkout.
- Platform admin customer subscription details and overview now expose past-due/cancelled/expired counts and grace/cancellation dates.
- Migration `20261104_0033_subscription_lifecycle.py` adds `grace_period_ends_at` and `cancellation_requested_at`.

### Increment 16 verification

- `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_lifecycle.py tests/test_billing_checkout_fulfillment.py tests/test_payment_reconciliation.py tests/test_platform_admin.py` — **18 passed**.
- `python -m compileall -q app tests` — passed.
- SQLite Alembic upgrade to head, downgrade to `20261104_0032`, re-upgrade to head, and `alembic check` — passed; no pending model changes.
- Frontend dependencies are absent; frontend lint, typecheck, Next production build and browser/mobile QA were not run.
- PostgreSQL 16, live Paystack test mode, Google Pay eligibility and deployed scheduled-job execution were not tested.

### Immediate deployment tasks (when deployment is available)

1. Apply `alembic upgrade head` (new head is `20261104_0033`).
2. Configure `BILLING_GRACE_PERIOD_DAYS=3` or another approved value from 0 to 14. Review this grace-period policy before public launch.
3. Configure a hosting scheduled job from the backend working directory: `python -m app.jobs.process_subscription_lifecycle`, every 15–60 minutes. Keep the existing payment reconciliation job scheduled separately every 5–10 minutes.
4. In Paystack test mode, test checkout success/failure, webhook delivery, cancellation at period end, cancellation reversal, renewal payment during grace, and expiry/downgrade.
5. Run the frontend dependency install, lint, TypeScript check, production build, and browser/mobile QA.
6. Validate migration and row-lock behavior on PostgreSQL 16 before production.

### Still outstanding

- Automatic recurring payment collection/Paystack subscription authorization and renewals. Current renewals are customer-initiated.
- Email/SMS renewal reminders and payment-failure notices.
- Refunds, disputes/chargebacks, settlement reconciliation, downloadable invoices/receipts and tax handling.
- Automated recovery of stale webhook receipts (Increment 14 retry is manual; Increment 15 reconciles pending payment attempts).
- PostgreSQL 16 concurrency validation, full frontend build/browser/mobile tests, live Paystack/Google Pay tests and deployment scheduler verification.
- PayPal and Flutterwave remain future providers; no checkout adapters have been activated.


## Latest increment — Increment 17 (2026-11-04)

**Paystack recurring-charge adapter foundation.** `backend/app/integrations/payments/paystack_checkout.py` now exposes `PaystackProvider.charge_authorization(...)`, which calls `POST /transaction/charge_authorization` using server-side credentials and a server-generated reference/amount/currency. It validates input and checks the returned reference. Focused verification: 17 tests passed across Paystack checkout, billing fulfillment, subscription lifecycle and payment reconciliation; no migration required.

**Not yet automatic recurring billing.** There is no recurring consent field/UI, no encrypted Paystack authorization persistence, no renewal-attempt table, no scheduled charge job, no 3DS challenge return flow, and no automatic subscription extension from a recurring debit. Do not describe or enable automatic renewal yet. Implement these in a later increment with explicit consent and verify every renewal transaction server-to-server before fulfillment. Paystack's reusable authorization flag and original authorization email are mandatory inputs; see `docs/paystack-billing.md`.


## Latest increment — Increment 18 (2026-11-04)

### Implemented

- Optional future-renewal authorization consent checkbox on `/billing`. The UI clearly says automatic renewal is not active yet and no future automatic charge will be made until the feature is activated and the customer is notified. Customers who do not consent still complete one-time checkout; no reusable authorization is retained for them.
- Checkout request schema accepts `recurring_consent` (false by default). The backend records consent timestamp, version (`paystack-recurring-v1`) and a server-authored wording snapshot on the payment transaction. It also includes a boolean consent marker in Paystack metadata.
- After server-side Paystack transaction verification, the fulfillment service stores an authorization only if the original payment has consent, Paystack returns `authorization.reusable is true`, an authorization code is present, and a dedicated billing encryption key is configured.
- The exact original checkout email is saved as `provider_authorization_email`. The authorization code is stored as Fernet ciphertext in `provider_authorization_code_encrypted`. Safe card display metadata includes last4/type/expiry only. PAN/CVV are never stored.
- Added `backend/app/integrations/billing_crypto.py` and setting `BILLING_AUTHORIZATION_ENCRYPTION_KEY`; keep the key backend-only and separate from `SOCIAL_TOKEN_ENCRYPTION_KEY`. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Losing the key makes stored authorization ciphertext unusable; rotation needs a controlled decrypt/re-encrypt process.
- Added migration `backend/migrations/versions/20261104_0034_recurring_authorization_consent.py` (down revision `20261104_0033`).

### Verification

- `cd backend && DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_billing_checkout_fulfillment.py tests/test_paystack_checkout.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py` — **20 passed**.
- `python -m compileall -q app tests migrations` — passed.
- File-backed SQLite Alembic `upgrade head` (0034), `downgrade 20261104_0033`, `upgrade head`, and `alembic check` — passed; no model/schema drift detected.
- The tests cover checkout consent capture, no-consent one-time checkout, and encrypted storage of a verified reusable authorization with original email/card metadata.
- Frontend `node_modules` is absent, so lint/typecheck/Next production build/browser/mobile QA were not run. PostgreSQL 16, live Paystack test mode, and production deployment were not run.

### Important boundary — do not enable automatic charging

Increment 18 does not implement renewal-attempt records, a renewal scheduler, recurring charge orchestration, server-side verification and atomic fulfillment of recurring debits, 3DS/customer challenge handling, bounded retry policy, renewal notices, or a customer-facing revoke-auto-renew control. The adapter primitive from Increment 17 must not be called by an unattended scheduler yet. Customers still initiate their next payment manually.

### Deployment notes

1. Before deploying, configure a valid `BILLING_AUTHORIZATION_ENCRYPTION_KEY` as a backend secret. If it is absent, checkout and initial payment activation still work, but reusable authorizations are not stored.
2. Apply `alembic upgrade head`; new head is `20261104_0034`.
3. Do not enable any scheduled recurring charges. Existing payment reconciliation and lifecycle schedulers remain separate.
4. Persistent file-backed SQLite migration upgrade/downgrade/re-upgrade and `alembic check` passed in this increment; validate PostgreSQL 16 locking/schema behavior before production.
5. Run Paystack test-mode checkout with and without consent; inspect only safe metadata and confirm reusable authorization is stored as ciphertext. Live provider test not performed in this increment.


## Current handover — Increment 19 (2026-11-04)

### Implemented
- Added `SubscriptionRenewalAttempt` and migration `20261104_0035_subscription_renewal_attempts.py`. A unique `(subscription_id, period_end)` constraint prevents more than one charge initiation for the same subscription period.
- Added `backend/app/modules/billing/renewals.py` with a bounded due-subscription processor. It requires active/past-due Paystack subscriptions, due period end, no scheduled cancellation, explicit recurring-consent evidence, Paystack reusable authorization, encrypted authorization code, and the original billing email.
- The processor persists the payment transaction and renewal attempt before contacting Paystack. Successful charge responses are followed by server-to-server verification through the existing `verify_and_activate` workflow.
- A Paystack pending/ongoing/OTP response is recorded as `needs_action`; no duplicate charge is sent for that period. An ambiguous timeout is marked `verification_pending`; subsequent runs perform verification only and never issue another charge for that period.
- Added `backend/app/jobs/process_subscription_renewals.py`. The new `BILLING_RENEWALS_ENABLED` flag defaults to `false`; the CLI returns without contacting Paystack unless explicitly enabled. Configuration validation requires Paystack secret and billing authorization encryption key if the flag is enabled.
- Updated billing guide, project status, known issues and decisions log.

### Remaining before automatic renewals can be enabled
1. Build customer-facing completion for Paystack authentication/challenge responses and a secure way for the owner to resume/complete a `needs_action` attempt.
2. Add advance renewal notices and failure/action-required notifications. The consent wording and launch notice must be reviewed before automatic billing begins.
3. Add customer self-service revocation/disable-renewal controls that also invalidate stored authorization.
4. Define and implement a provider-safe bounded retry policy; do not retry an ambiguous charge without verification.
5. Run Paystack test-mode recurring charges, declines, pending/OTP challenges and webhook/verify race tests.
6. Verify PostgreSQL 16 uniqueness/locking behavior and scheduler single-instance deployment; no multi-replica concurrency test has been run.
7. Keep `BILLING_RENEWALS_ENABLED=false` until all items above are complete and explicitly approved.

### Verification in Increment 19
- Exact focused command from `backend/`: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_billing_checkout_fulfillment.py tests/test_paystack_checkout.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py tests/test_billing_price_admin.py tests/test_billing_readiness.py tests/test_paystack_signatures.py tests/test_paystack_transactions.py tests/test_platform_admin.py` — **54 passed in 3.89s** using SQLite and mocked Paystack responses.
- `python -m compileall -q app tests` — passed.
- Migration `20261104_0035` upgrade, downgrade to `20261104_0034`, and re-upgrade passed on file-backed SQLite.
- The complete backend test suite was attempted twice but did not finish within the execution time limit; the latest run reached approximately 64% before timeout. Do not report the full suite as passed.
- Live Paystack, PostgreSQL 16, frontend build/browser QA, scheduler hosting configuration and production operations remain unverified.

### Next recommended increment
Increment 21: customer-facing renewal management and Paystack customer-action handling, including safe renewal status visibility, a secure owner-only challenge handoff, cancellation/revocation of stored authorizations, and renewal email notifications. Do not enable scheduled charging as part of Increment 21 until its acceptance tests pass.


## Current handover — Increment 20 (2026-11-04)

### Platform-admin customer spending leaderboard
- New endpoint: `GET /api/v1/platform-admin/top-customers?currency=NGN|USD&sort=desc|asc&limit=10`. It uses the existing `require_platform_admin` verified-email allowlist dependency.
- Ranking is based on lifetime successful payment amount (`SUM(amount_minor)` where `status=paid`), grouped by `initiated_by_user_id`. It returns ranks, customer name/email/account status, total spend, currency, successful payment count and latest paid timestamp. Pending/failed payments are excluded.
- `/platform` now renders the top 10 customers and provides highest-spend-first / lowest-spend-first sorting plus NGN/USD selection. The data refreshes when either selector changes.
- NGN and USD are ranked independently. There is no cross-currency total because the project has no approved FX source or conversion policy.
- Attribution currently follows the user who initiated checkout, which is the payer recorded on each transaction. It does not distribute workspace payments to every organization member.
- No migration is required. The implementation is backend + frontend, not backend-only.

### Increment 20 verification
- `cd backend && DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_platform_admin.py` — **8 passed**. Tests cover ranking, top-10 truncation, ascending/descending order, pending exclusion, currency separation and non-admin denial.
- Python compileall and frontend static checks are recorded in the increment archive notes if run; do not infer a frontend build. `frontend/node_modules` is absent in this environment, so ESLint, TypeScript, Next production build and browser/mobile QA were not run. PostgreSQL 16 and production behavior remain unverified.

### Next steps
1. Finish customer-facing recurring renewal action/3DS flow and revoke-auto-renew controls.
2. Add renewal notices and safe bounded retries; keep `BILLING_RENEWALS_ENABLED=false` until reviewed and test-mode validated.
3. Add refunds/chargebacks before treating leaderboard spend as net revenue; until then it is gross successful payment volume.
4. Run frontend build/browser/mobile QA and PostgreSQL 16 integration tests.


## Current handover — Increment 21 (2026-11-04)

### Implemented
- Added `PaystackProvider.deactivate_authorization()` using the documented Paystack `POST /customer/authorization/deactivate` endpoint. It sends the authorization code only from the backend using the Paystack secret key.
- Added owner-only endpoint `POST /api/v1/billing/organizations/{organization_id}/subscription/authorization/revoke`. It is tenant-scoped, decrypts authorization server-side, calls Paystack, and only clears the local ciphertext and safe card metadata after a confirmed provider response.
- Failed or ambiguous provider deactivation retains the encrypted authorization and returns an error; the app does not claim it was revoked.
- The subscription read response includes `authorization_saved`, `authorization_card_last4`, `authorization_card_type`, and `recurring_consent_recorded`. It never returns the authorization code or encrypted bytes.
- `/billing` now displays a saved-payment-authorization panel and an owner-only “Deactivate saved method” control. The confirmation explains this does not cancel current paid access.
- Historical consent timestamp/version remain for audit after revocation; local reusable authorization and card display metadata are cleared. No migration required.

### Increment 21 verification
- `cd backend && DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_paystack_checkout.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py` — **24 passed in 2.54s**.
- `python -m compileall -q app tests migrations` — passed.
- ZIP integrity checked after packaging.
- Frontend dependency install/lint/typecheck/production build/browser/mobile QA were not run because frontend dependencies are not present. PostgreSQL 16 and live Paystack test mode were not run.

### Still outstanding before enabling automatic renewals (updated by Increments 22–23)
1. [x] Customer OTP/3DS/action-required completion and secure verification return path (Increment 22).
2. [x] Advance renewal notices, action-required and failure emails, and durable delivery tracking with a per-subscription pre-charge notice gate (Increment 23).
3. [ ] Safe bounded payment retry policy with verification-first handling of ambiguous outcomes; never blindly charge again for the same period.
4. [ ] Live Paystack test-mode deactivation, renewal success/decline/pending/OTP and webhook/verify race tests.
5. [ ] PostgreSQL 16 locking/unique-constraint tests and a single-worker scheduler deployment/monitoring plan.
6. [ ] Frontend install, lint, typecheck, production build, and browser/mobile QA.
7. Keep `BILLING_RENEWALS_ENABLED=false` until remaining items are implemented, tested and explicitly approved.


## Current handover — Increment 22 (2026-11-04)

### Implemented in this increment
- `SubscriptionRenewalAttempt.authorization_url` stores a Paystack-hosted challenge link only when the returned URL is HTTPS and its exact hostname is `checkout.paystack.com`. Migration: `20261104_0036_renewal_customer_authentication.py` (down revision `20261104_0035`).
- Renewal charge requests include a callback URL back to `/billing?renewal_reference=<our durable payment reference>`. The adapter accepts an optional `callback_url` and includes it in Paystack's charge-authorization request.
- `GET /api/v1/billing/organizations/{organization_id}/renewal-actions` returns action-required attempts. All workspace members can see the status; only owner/admin roles receive the hosted authentication URL.
- `POST /api/v1/billing/organizations/{organization_id}/renewal-actions/{reference}/verify` is owner/admin-only and checks tenant ownership and durable attempt state. It invokes server-to-server Paystack verification through `verify_and_activate`; browser return is never treated as payment proof. On verified success, the subscription period is extended and the challenge URL is cleared. A not-yet-confirmed result remains actionable; a confirmed decline marks the attempt failed.
- `/billing` now displays the action-required panel, opens Paystack authentication in a separate tab, supports manual verification, and automatically attempts verification after Paystack returns with `renewal_reference`. It reloads subscription and payment history after the attempt.

### Verification in Increment 22
- `cd backend && DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_paystack_checkout.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py tests/test_platform_admin.py` — **39 passed in 5.31s** (SQLite and mocked provider responses).
- `python -m compileall -q backend/app backend/tests` — passed.
- File-backed SQLite migration `upgrade head`, `downgrade 20261104_0035`, `upgrade head`, and `alembic check` — passed; no new upgrade operations detected.
- `unzip -t` — passed for the packaged archive.
- Not run: frontend npm build/typecheck/lint/browser/mobile QA (`frontend/node_modules` absent), PostgreSQL 16, live Paystack test-mode charge, real issuer OTP/3DS, production callback configuration, and scheduler operations.

### Still required after Increment 22 (updated by Increment 23)
- [x] Advance renewal notices, payment-failure and action-required email notifications, durable delivery state and a pre-charge notice gate — implemented in Increment 23.
- [ ] Define and validate a provider-safe payment retry policy; never retry ambiguous timeouts or action-required attempts without verification and an approved customer decision. SMTP retry behavior is separate from payment retry behavior.
- [ ] Validate the full Paystack test-mode flow for success, decline, paused challenge, customer cancellation, webhook/verify races, and repeated callback delivery.
- [ ] Run PostgreSQL 16 migration and concurrency tests; configure a supervised single scheduler invocation and operational alerting.
- [ ] Install frontend dependencies deterministically, run TypeScript/ESLint/Next production build, and perform desktop/mobile browser tests.
- [ ] Review customer consent wording, renewal notices, cancellation window and merchant/legal requirements before enabling automatic charges.

**Keep `BILLING_RENEWALS_ENABLED=false`.** Increment 23 adds a per-subscription notice-delivery gate, but recurring collection is not approved for production until provider, database, SMTP and scheduler validation is complete.


## Latest increment — Increment 23 (2026-11-04)

### Implemented
- Added `BillingNotification` and migration `20261104_0037_billing_notification_outbox.py`. The outbox records event type, recipient, subject/body, delivery state, attempt count, next attempt, sent time and a unique idempotency key.
- Added migration `20261104_0038_recurring_billing_notice_gate.py` and `Subscription.recurring_billing_notice_sent_at`. The renewal worker now excludes any subscription without a successfully delivered activation notice. A new or replaced reusable authorization resets the notice timestamp; confirmed authorization revocation also clears it.
- Added a one-time automatic-renewal activation notice for opted-in subscriptions, followed by configurable advance reminders (default three days) for subsequent renewals. If the activation notice itself is sent inside the reminder window, a second email for the same cycle is suppressed.
- Added action-required and failed-payment email events. The Paystack challenge flow and the renewal decline path enqueue notifications in the same database transaction as their billing state changes.
- Added `backend/app/jobs/process_billing_notifications.py`. Run it daily or every few hours, before the renewal worker. It queues notices and processes a bounded SMTP batch.
- SMTP failures retry at 1, 5, 30 and 120-minute intervals, with a maximum of five delivery attempts. Stale `sending` claims are eligible for recovery after 20 minutes. The outbox is at-least-once: a process crash after SMTP acceptance but before the database commit can cause a duplicate message.
- Added settings `BILLING_RENEWAL_NOTIFICATIONS_ENABLED` (default false) and `BILLING_RENEWAL_REMINDER_DAYS` (default 3, range 1–14). Enabling automatic renewals now also requires notifications enabled and `SMTP_HOST` configured.
- This increment is backend-only; no frontend page or UI was changed.

### Verification
- Exact focused command from `backend/`: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_billing_notifications.py tests/test_subscription_renewals.py tests/test_paystack_checkout.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py tests/test_platform_admin.py tests/test_config.py tests/test_production_config.py` — **57 passed**.
- `python -m compileall -q app tests migrations` — passed.
- File-backed SQLite migration `upgrade head`, `downgrade 20261104_0037`, `upgrade head`, and `alembic check` — passed; no model/schema drift detected.
- SMTP delivery was mocked in tests. Actual SMTP credentials/delivery, PostgreSQL 16, live Paystack, frontend build/browser QA and deployment scheduler execution were not tested.

### Required deployment settings and schedule
- Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`/`SMTP_PASSWORD` as required by the provider, `SMTP_USE_STARTTLS`, and `EMAIL_FROM`.
- Set `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=true` only after SMTP settings are verified. Run `python -m app.jobs.process_billing_notifications` daily or every few hours and confirm activation notices are delivered.
- Keep `BILLING_RENEWALS_ENABLED=false`. It remains a separate manual activation decision and will be rejected by configuration unless notifications are enabled and SMTP host is present. Even when enabled, subscriptions without a delivered activation notice cannot be charged.
- Do not enable automatic renewals until live Paystack test-mode challenge/decline/success cases, PostgreSQL concurrency, SMTP deliverability and scheduler single-instance operation have been verified and approved.


## Latest increment — Increment 24 (2026-11-04)

### Implemented
- Added verification-only reconciliation for existing automatic-renewal attempts in `backend/app/modules/billing/renewal_reconciliation.py`.
- Added CLI: `python -m app.jobs.reconcile_subscription_renewals` (run from `backend/`). Recommended schedule: every 5–10 minutes, separately from the charge worker.
- Scans `verification_pending` attempts and `processing` attempts older than ten minutes in bounded batches (default 50, maximum 200). A stale processing row is first marked verification-pending, then the existing Paystack reference is checked directly.
- Never calls the authorization charge endpoint and never creates a new payment reference. Provider success goes through the existing trusted amount/currency/reference/email verification and subscription fulfillment path. Provider-confirmed decline updates the attempt and queues the existing failure notice. Outages/mismatches remain pending or attention-required.
- No migration and no frontend change.

### Verification
- Focused command from `backend/`: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_billing_notifications.py tests/test_payment_reconciliation.py tests/test_subscription_lifecycle.py tests/test_billing_checkout_fulfillment.py tests/test_paystack_checkout.py` — **43 passed in 4.73s**.
- `python -m compileall -q app tests migrations` — passed.
- File-backed SQLite Alembic `upgrade head`, `downgrade 20261104_0038`, `upgrade head`, and `alembic check` — passed; no schema drift detected.
- PostgreSQL 16, live Paystack, real SMTP, scheduler supervision and frontend build/browser QA were not tested.

### Operational safeguards
- This recovery CLI can run while `BILLING_RENEWALS_ENABLED=false` because it only verifies existing references and cannot charge.
- Keep `BILLING_RENEWALS_ENABLED=false`. No automatic payment retry is enabled. A declined, ambiguous or action-required attempt is not charged again in the same period.
- If a stale attempt remains pending because Paystack cannot find/verify the reference, investigate it manually; do not delete the ledger row or create another charge for the same subscription period.


## Current handover — Increment 25 (2026-11-05)

### Implemented
- Migration `20261104_0039_provider_directed_renewal_retry.py` adds nullable `retry_at`, non-null `retry_count` (default 0), nullable `previous_reference` for audit, and index `ix_renewal_attempt_retry_at`.
- `backend/app/integrations/payments/paystack_checkout.py` defines `PaystackRetryWindowError`. The adapter only emits it when the response explicitly supplies Paystack's recurring-card regulator retry window. It accepts timezone-aware `retry_by` or the documented explicit “Charge attempt cannot be fulfilled until X minutes” message. It does not infer retry eligibility from a generic HTTP error.
- `backend/app/modules/billing/renewals.py` can schedule one delayed retry per billing period. It waits for the provider's stated window, checks that the subscription is still on the same period, not cancelled, consented and has an active reusable authorization, and generates a fresh Paystack reference for the retry while preserving the rejected reference in `previous_reference`. A second regulator restriction ends the retry path. This follows Paystack's unique-reference requirement rather than reusing a reference that may already have been recorded.
- Ambiguous timeouts remain verification-only; OTP/3DS and ordinary declines are not automatically retried. A provider-directed retry is a narrow implementation of Paystack's documented regulator wait response, not evidence of separate Paystack merchant approval. Validate in test mode and with Paystack before enabling recurring collection.
- Added `backend/app/jobs/run_billing_maintenance.py`, a unified bounded job that queues/delivers billing notices, reconciles uncertain references, runs due provider-directed retries, invokes due renewal processing only if `BILLING_RENEWALS_ENABLED=true`, and runs subscription lifecycle transitions. It emits one JSON summary and exits non-zero on infrastructure errors.
- `backend/render.yaml` now includes a five-minute Render cron service. Both billing flags are explicitly false. It requires the same production DB/security environment as the API. Keep a single scheduler service; do not run duplicate cron providers.
- Added `backend/app/jobs/check_billing_readiness.py`. It checks DB connectivity and can send one explicit SMTP smoke-test email using `--email-to` to a controlled inbox. It never sends email without that argument.
- Added `docs/operations/billing-scheduler.md` with Render log/alert instructions, schedule ordering, environment requirements and manual recovery commands.
- Added a PostgreSQL-gated test that verifies the database unique constraint prevents two renewal-attempt records for the same subscription period. It runs in CI when `TEST_POSTGRES_URL` is present; it was skipped in this local environment.

### Verification in Increment 25
- `cd backend && DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_subscription_renewals.py tests/test_paystack_checkout.py tests/test_billing_notifications.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py tests/test_platform_admin.py tests/test_config.py tests/test_production_config.py tests/test_postgres_connection.py tests/test_postgres_integration.py` — **65 passed, 3 skipped in 7.85s**.
- `python -m compileall -q app tests migrations` — passed.
- File-backed SQLite Alembic `upgrade head`, `downgrade 20261104_0038`, `upgrade head`, and `alembic check` — passed; no model/schema drift detected.
- Mocked SMTP transport verifies STARTTLS, authentication and message submission. This is not a real provider/inbox delivery test.
- Not run: PostgreSQL 16 concurrency, live Paystack test-mode retry/regulator and OTP/3DS, actual SMTP delivery, Render cron deployment and alert delivery, frontend build/typecheck/lint/browser/mobile QA.

### Owner-side items still required
1. Configure SMTP and run `python -m app.jobs.check_billing_readiness --email-to <controlled-inbox>`; verify inbox and spam folder.
2. Deploy the Render cron service (or equivalent single managed scheduler) and confirm five-minute successful runs and failure alerts.
3. Run migrations through `20261104_0039` against the real PostgreSQL database and run PostgreSQL concurrency tests.
4. Run Paystack test-mode charge success, regulator wait/retry, decline, timeout, OTP/3DS, webhook/verify race and duplicate-callback scenarios.
5. Install frontend dependencies, run lint/typecheck/build, and test desktop/mobile billing flows.

**Keep `BILLING_RENEWALS_ENABLED=false` and `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` until owner-side verification is complete.**


## Current handover — Increment 26 (2026-11-05)

### What changed
- Increment 26 was a stabilisation/verification and documentation increment only. No application code or migration was changed.
- The original blueprint remains at `docs/full-project-blueprint.md`; do not add a duplicate.
- Product scope remains the shared foundation and Product 01 Social Media Automation only.

### Verified locally
- Runtime used: Python 3.13.5; Node 22.16.0; npm 10.9.2. Project declares Python >=3.12 and CI uses Python 3.12.
- `python -m compileall -q app tests` passed.
- All 51 backend test files passed when split into two bounded groups: 178 passed in group one; 183 passed and 3 skipped in group two. Total: **361 passed, 3 skipped**. The skipped cases require PostgreSQL.
- `tests/test_scheduling.py`: 20 passed.
- SQLite Alembic upgrade to `20261104_0039`, downgrade to `20261104_0038`, re-upgrade to head and `alembic check`: passed; no new upgrade operations detected.

### Still unverified / next actions
1. Generate and review `frontend/package-lock.json` in a network-enabled Node 22/npm 10 environment; commit it so installs can use `npm ci`.
2. Install frontend dependencies, then run `npm run lint`, `npx tsc --noEmit`, and `npm run build`. Add/fix the TypeScript script if needed only after inspecting the result.
3. Run desktop/mobile browser QA for registration, login, workspaces, onboarding, business profile/products, AI drafts, social connections, publishing, scheduling/calendar, Brand Intelligence and billing.
4. Inspect the actual GitHub Actions run using Python 3.12, Node 22 and PostgreSQL 16. Run PostgreSQL integration tests only against the disposable CI database; `test_postgres_integration.py` drops and recreates schema tables.
5. Complete live Meta, Instagram, TikTok, Google/YouTube, Paystack and SMTP test-mode verification with the correct developer apps, scopes and test accounts.
6. Verify the single Render billing cron service, SMTP delivery/readiness and failure alerts before considering billing automation activation.
7. Keep `BILLING_RENEWALS_ENABLED=false` and `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` until all required billing verification and owner approval are complete.

See `increment-26-stabilisation-audit-2026-11-05.md` for exact commands, output interpretation and environment limitations. The 361/3 result is a partitioned SQLite test result, not a PostgreSQL or production verification claim.


## Future lead generation and live progress requirements (captured 2026-11-05)

The owner has approved the future direction for an AI-assisted lead-generation pipeline and a customer-visible, stage-by-stage progress interface. Read these before planning the relevant future products:
- `docs/products/product-02-lead-management/requirements.md`
- `docs/products/product-06-data-collection/requirements.md`
- `docs/products/product-04-email-marketing/requirements.md`
- `docs/architecture/background-job-progress.md`

The frontend must show real backend job progress (not a simulated animation): target understanding, business discovery, contact extraction/enrichment, cleaning/deduplication, email quality checks, qualification/scoring, optional outreach drafting/review, customer approval, sending, and later performance analysis. Persist job/stage state and events so users can return to the page and reconnect. Prefer SSE with replay/snapshot support and polling fallback. Inspect the existing Brand Intelligence sync-job pattern before creating a generic job framework.

Important: these are future requirements only. Current scope remains foundation hardening and Product 01. Do not start Product 02/04/06 implementation until project status and the owner explicitly authorize the scope change.


## Current handover — Increment 29 (2026-11-05)

### What changed
- Destructive PostgreSQL integration tests now call `_disposable_postgres_engine()` before dropping/recreating application tables. The helper requires `TEST_POSTGRES_ALLOW_DESTRUCTIVE=1`, a local test host (`localhost`, `127.0.0.1`, or `postgres`), and database name `ci_db` or `test_*`.
- Three tests cover rejection of missing opt-in, non-test database name, and remote host. GitHub Actions sets the opt-in only in its isolated PostgreSQL 16 job.
- No application feature, database migration, billing behavior, or production configuration was changed.

### Verification
- All 51 backend test files: **364 passed, 3 skipped** across two bounded partitions (178 passed; 186 passed, 3 skipped).
- Python compilation passed.
- SQLite Alembic upgrade to `20261104_0039`, downgrade to `20261104_0038`, re-upgrade to head, and `alembic check`: passed; no new operations detected.
- The 3 PostgreSQL-gated tests were skipped. No Docker/psql/pg_isready executable or psycopg driver was available here. GitHub Actions PostgreSQL 16 was inspected but no workflow run was observed.

### Frontend lockfile status — still outstanding
- `frontend/package.json` is present; `frontend/package-lock.json` and `node_modules` are absent.
- Node 22.16.0 and npm 10.9.2 are available. Genuine `npm install --package-lock-only` attempts timed out after npm reported `EAI_AGAIN registry.npmjs.org`. No synthetic lockfile was created.
- Once registry access is restored: run `npm install --package-lock-only --ignore-scripts --no-audit --no-fund`, inspect and commit the generated lockfile, change the frontend CI install command to `npm ci`, then run `npm ci`, `npm run lint`, `npm run typecheck`, and `npm run build`.
- Until that happens, do not claim the frontend build is verified and do not switch CI to `npm ci` because it would fail without the lockfile.

### Next actions
1. Re-run lockfile generation in a network-enabled Node 22/npm 10 environment.
2. Observe and inspect the actual GitHub Actions PostgreSQL 16 test and migration job.
3. Run frontend install/lint/typecheck/build and browser/mobile QA after lockfile creation.
4. Continue the live SMTP, Paystack test-mode, scheduler, and provider checks already listed in this handover.

**Billing safety:** Keep `BILLING_RENEWALS_ENABLED=false` and `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` until the owner-side verification and approval gates are satisfied.

## Current handover — Increment 30 (2026-11-05)

### What changed
- **Invitation resend:** `POST /organizations/{id}/invitations/{invitation_id}/resend` (owner/admin). New token (old link dies), expiry +7 days, cooldown `INVITATION_RESEND_COOLDOWN_SECONDS` (default 60, HTTP 429 + `Retry-After`), refuses accepted invitations, activity action `organization.invitation_resent`. Migration `20261105_0040` adds `organization_invitations.last_sent_at` (set on create and resend).
- Admin invitation list now includes `status` (`pending`/`accepted`/`expired`) and `last_sent_at`. Admins cannot revoke or resend admin-role invitations (owners only).
- Accepting an invitation sets `email_verified_at` if unset.
- **Rule-based brand analysis:** `?method=rules` on `/brand-intelligence/analyze` (`app/modules/brand_intelligence/heuristics.py`). Same proposal keys as the AI mode plus `evidence_level`, `suggestions`, `metrics`, `method`; `proposed_voice` stays empty; `model="rule-based"`. Default mode and its 503-without-provider behavior are unchanged. Topic extraction uses an English stop-word list.
- **Frontend:** Resend button and status/expiry text in the workspace invitation list; `src/lib/invitation-helpers.ts`; Vitest (`npm test`, `vitest.config.ts`, `vitest` devDependency) and an "Unit tests" CI step.

### Verification (honest)
- Ran: `compileall` (pass), undefined-name scan (clean), `tests/test_brand_rules.py` pure tests (12 passed), frontend helper tests via `tsc` + Node shim (4 passed).
- **Not run:** 7 new API tests (4 in `test_organizations.py`, 3 in `test_brand_intelligence.py`), the existing 364-test suite after these changes, migration `0040`, `npm install`/lint/typecheck/build/`npm test`, browser QA.

### Next actions
1. Run the full backend suite and `alembic upgrade head` + `alembic check` (head is now `20261105_0040`); fix any failures in the new tests.
2. After lockfile generation (still outstanding), run `npm ci`, `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`.
3. Browser-test the workspace invitation list (resend, revoke, expired state).
4. Decide whether the dashboard should offer the rules-based analysis button; today it is API-only.

## Latest increment — Platform intelligence and financial monitoring

See `docs/project-management/increment-43-platform-intelligence-financial-monitoring-2026-11-07.md` for the current admin-console extension, login telemetry model/migration, financial analytics API, global activity feed, enriched customer inspection, limitations, and next implementation steps. Run `alembic upgrade head` before using the new login-event endpoints. Financial figures are confirmed gross receipts by currency; operating costs/profit are explicitly unavailable until cost/refund/chargeback ledgers exist.

Increment 43 also includes a manual verified operating-cost ledger (`platform_cost_entries`, migration `20261107_0044`) for hosting, AI provider, image/video, storage, messaging and other expenses. See the Increment 43 report for endpoints, limits and the important distinction between recorded costs and complete profitability.

## Current handover — Increment 44 (2026-11-07)

Successful platform login telemetry now covers all current authentication methods: password, Google and WhatsApp. All three paths use a shared best-effort helper; telemetry write failures do not block sign-in. The existing admin login-history views expose the method field, so no schema migration is needed. Raw IPs, credentials, one-time codes, provider tokens and provider subjects are not stored. Failed-login telemetry remains deliberately deferred pending a privacy/retention design. See `increment-44-provider-aware-login-telemetry-2026-11-07.md`.

## Increment 45 — provider-reported AI token metering (2026-11-07)

See `increment-45-ai-token-metering-2026-11-07.md`. Successful OpenAI content caption, video-script, and AI brand-analysis calls now persist provider-reported prompt/completion/total token counts by organization, user, model, provider, and feature. The platform financial endpoint and admin panel expose grouped usage. Estimated USD cost is intentionally null unless both per-million-token rates are explicitly configured for the active model using `OPENAI_INPUT_USD_PER_MILLION_TOKENS` and `OPENAI_OUTPUT_USD_PER_MILLION_TOKENS`; zero/default rates disable cost estimation, not token collection. Migration `20261107_0045` follows `0044`.


## Latest update — Increment 46 (2026-11-07)

See `increment-46-refund-chargeback-reconciliation-2026-11-07.md`. Signed Paystack refund and dispute webhook outcomes are now stored in an idempotent payment-adjustment ledger and surfaced in platform financial reporting. Net profit remains intentionally unavailable pending provider fee/reversal reconciliation and a complete operating-cost ledger. Validate exact dispute-resolution payload semantics in Paystack sandbox before relying on them for accounting.


## Latest update — Increment 47 (2026-11-07)

Platform administrator APIs now require enrolled TOTP MFA. Enrolled platform administrators must authenticate with password plus a valid authenticator code; OAuth/WhatsApp sign-in cannot bypass this requirement. Enabling TOTP invalidates existing sessions so administrators must sign in again. See `increment-47-platform-admin-mfa-hardening-2026-11-07.md` for deployment and enrollment steps. The verified-email `PLATFORM_ADMIN_EMAILS` allowlist remains the source of platform-owner identity; granular delegated admin roles and recovery-code/dual-control workflows remain future work.

## Increment 48 — delegated platform administrator roles (2026-11-07)

- Added `platform_admin_roles` and migration `20261107_0047` for delegated administrator assignments. The configured `PLATFORM_ADMIN_EMAILS` accounts remain implicit owner-level administrators and are not stored as delegated roles.
- Added backend permission dependencies. Roles: `support` (customer inspection, customer support actions, activity and login history), `finance` (financial reports, AI usage, payment adjustments and cost ledger management), `operations` (operational diagnostics and bounded payment/webhook operations), and `viewer` (overview, customer list, activity and login history).
- Sensitive role grants/revocations are owner-only, require verified active registered users, and are audited. Delegated roles cannot grant other roles or access the billing-price mutation endpoints.
- MFA is mandatory for delegated administrators too. Password login validates authenticator codes; Google/WhatsApp sign-in cannot issue an admin session. API access independently checks MFA and role permission, so hiding UI controls is not the security boundary.
- Frontend platform page includes owner-only delegated-role management.
- Deployment: run Alembic migration `20261107_0047` after `0046`. Assign roles only to trusted accounts; all delegated admins must enroll MFA before use.

## Increment 49 — administrator security monitoring and owner email campaigns (2026-11-07)

See `increment-49-admin-security-and-email-campaigns-2026-11-07.md`. Migration `20261107_0048` adds IP/success fields to login telemetry and campaign/recipient delivery ledgers. Owner-only admin UI now shows recent administrator sign-ins, failed admin sign-ins, account-wide session revocation, campaign composition/history and recipient delivery totals. Campaigns target registered users with verified email addresses and require configured SMTP; sending is queued in FastAPI background batches of 25. SMTP acceptance is not guaranteed inbox delivery. This is a process-local background task, not a durable queue; production should move it to the durable worker/outbox, add bounce/unsubscribe support before marketing use, and define IP retention. Fresh SQLite Alembic upgrade and Python compilation passed; pytest was blocked by missing `pyotp`; frontend build/typecheck and live SMTP remain unverified.

## Current handover — Increment 50 (2026-11-07)

Email campaigns are now database-queued and processed by the repeatable scheduler `cd backend && python -m scripts.process_email_campaigns`; this replaces the process-local FastAPI background task. Migration `20261107_0049` adds bounded retry state, per-recipient unsubscribe capabilities and a global suppression table. Owner APIs expose campaign analytics and retry of permanently failed recipients. The `/email/unsubscribe` frontend page posts to the public unsubscribe endpoint; future campaigns exclude suppressed addresses. Run exactly one worker instance (no distributed lease is implemented). SMTP acceptance is not inbox delivery; provider bounce/complaint webhooks and true delivery/open/click analytics remain outstanding. See `increment-50-email-campaign-durability-unsubscribe-2026-11-07.md` for operational instructions and limitations.

## Increment 51 — Resend campaign provider
- Read `increment-51-resend-campaign-provider-2026-11-07.md` before changing campaign delivery.
- Campaigns can use `EMAIL_CAMPAIGN_PROVIDER=smtp` (default) or `resend`. Configure `RESEND_API_KEY` and a verified `EMAIL_FROM` when using Resend.
- Transactional password-reset, verification and billing messages still use SMTP; do not remove SMTP settings without migrating and validating those flows separately.
- Configure the signed Resend webhook at `/api/v1/platform-admin/public/email/resend-webhook` and set `RESEND_WEBHOOK_SECRET`. Subscribe to delivered, bounced and complained events.
- Migration head is `20261107_0050`.


## Latest handover — Increment 52 (2026-11-07)

- Campaign worker coordination now uses the singleton `platform_email_worker_leases` table (migration `20261107_0051`). A conditional atomic update prevents overlapping campaign workers from claiming the queue. Lease is 15 minutes and renews between recipients; after a crash, a later scheduler run can resume after expiry.
- Resend events that arrive before the worker commits the provider message ID are replayed after correlation is saved. Bounce and complaint outcomes continue to add global suppression.
- Verification: Python compile passed; fresh SQLite migration, downgrade to `20261107_0050`, re-upgrade, and `alembic check` passed; empty queue CLI and SQLite lease contention/release smoke checks passed.
- Not verified: PostgreSQL multi-process concurrency, live Resend event ordering/signatures, complete backend test suite, frontend lint/typecheck/build/browser QA, and production deployment.
- Continue scheduling `python -m scripts.process_email_campaigns` from `backend/`. Use a shared production database for all scheduler instances. SMTP mode remains at-least-once; Resend idempotency is bounded by the provider's retention window.
- Next: add automated API/worker regression tests for lease contention, lease expiry recovery, webhook-before-message-ID reconciliation, and bounce/complaint suppression; then run them against PostgreSQL as well as SQLite.

## Latest increment — 53: separate admin demo login

- Customer demo remains at `/login` and keeps the existing seeded demo credentials.
- Platform-owner demo entry is `/admin/login`; with backend `DEMO_MODE=true`, use **Enter administrator demo** to create a demo owner session and open `/platform`.
- The UI calls `POST /api/v1/auth/demo-admin`. The backend returns 404 when demo mode is off and only issues a session to the separate seeded `DEMO_ADMIN_EMAIL` identity. `DEMO_EMAIL` remains a customer-only demo identity and must never be included in `PLATFORM_ADMIN_EMAILS`.
- This is a demo-only MFA exception, enforced server-side in the shared platform-admin authorization dependency. Production configuration refuses demo mode, and production owner/delegated admin MFA remains unchanged.
- See `increment-53-separate-admin-demo-access-2026-11-07.md` for implementation and verification details.


### Increment 54 — Demo identity separation

The customer demo (`DEMO_EMAIL`, default `customer-demo@example.com`) and platform-owner demo (`DEMO_ADMIN_EMAIL`, default `platform-owner-demo@example.com`) are distinct users with separate workspaces. `/login` signs into the customer demo; `/admin/login` calls `POST /api/v1/auth/demo-admin` for the platform-owner demo and redirects to `/platform`. Do not add the customer demo email to `PLATFORM_ADMIN_EMAILS`. Demo mode remains restricted to isolated SQLite and non-production `APP_ENV`.
