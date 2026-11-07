## Increment 29 update — 2026-11-05
- The destructive PostgreSQL integration tests now require explicit `TEST_POSTGRES_ALLOW_DESTRUCTIVE=1`, a local test host, and a database named `ci_db` or prefixed `test_`. CI opts in only for its isolated PostgreSQL 16 service. This guard reduces risk but does not make it safe to use production credentials.
- PostgreSQL 16 still has not been executed in this runtime. The 3 PostgreSQL-gated tests remain skipped; inspect the actual GitHub Actions result before marking the database gate verified.
- `frontend/package-lock.json` remains absent. Increment 29 retried genuine generation with Node 22.16.0/npm 10.9.2, but npm registry DNS resolution failed (`EAI_AGAIN registry.npmjs.org`) and attempts timed out. No fake lockfile was created. Retry when registry access is available; then run `npm ci`, lint, typecheck, and build. Change CI to `npm ci` only after the lockfile is committed.
- Frontend dependencies, ESLint, installed-project TypeScript check, Next.js build, and browser/mobile QA remain unverified.

## Current frontend verification blocker — Increment 27 (2026-11-05)

- `frontend/package-lock.json` is not present. The project has no cached npm package metadata in the current execution environment; registry access failed DNS resolution with `EAI_AGAIN registry.npmjs.org`.
- Do not fabricate a lockfile. Generate and review a real lockfile with Node 22/npm 10 in a network-enabled environment.
- Frontend lint, TypeScript, Next.js build, and browser/mobile QA remain unverified. Increment 27 added an explicit typecheck script and CI step, but the workflow has not been run.

# Known Issues and Verification Tasks

## Verification still required
- Increment 26 reran all 51 backend test files in two bounded partitions on SQLite/Python 3.13.5: **361 passed, 3 skipped**. Python compilation passed. The skipped tests require PostgreSQL. Re-run in the declared Python 3.12 CI environment and inspect the actual CI result. See `increment-26-stabilisation-audit-2026-11-05.md`.
- PostgreSQL 16 application integration remains unverified locally. PostgreSQL-gated integration tests were skipped because `TEST_POSTGRES_URL` was not set and no local PostgreSQL service/client is available. Increment 26 verified SQLite Alembic upgrade to `20261104_0039`, downgrade to `20261104_0038`, re-upgrade, and `alembic check` with no schema drift. SQLite does not prove PostgreSQL compatibility.
- Frontend dependencies remain absent. Increment 26 confirmed there is no `frontend/package-lock.json`; offline lockfile generation failed because npm package metadata was not cached and registry access was unavailable. `npm run lint` and `npm run build` both exit 127 (`eslint`/`next` not found). TypeScript validation and browser/mobile QA remain unverified. Tailwind v4 and its PostCSS plugin are declared and configured.
- The GitHub Actions workflow exists, but the first GitHub CI run has not been observed.
- Hosting provider configuration and live deployment remain unverified.

## Security and operational limitations
- Authentication is still an initial implementation: email verification links and optional login enforcement are implemented (migration `20261104_0026`), but production SMTP delivery and frontend build/browser QA remain unverified; refresh tokens and a reviewed Secure/HttpOnly-cookie session flow are also outstanding. Logout, sign-out-everywhere, change password and password reset exist (2026-11-04) but have only been tested in code review and unit tests that could not be run in the authoring environment; verify before relying on them. Do not expose this as a finished commercial application.
- Password reset needs working SMTP (`SMTP_*`, `EMAIL_FROM`, `FRONTEND_BASE_URL`) and has not been tested against a real mail provider. Reset/change-password rate limits are in-memory like the login limiter (not shared across workers; move to Redis). Every access token is checked against the database on each request (user row plus the revoked-token table).
- Login rate limiting and AI generation hourly limits are in-memory: counters reset on restart and are not shared across workers. The failed-attempt limiter caps its local key map at 10,000 keys. At capacity it never evicts blocked keys and evicts unblocked keys fewest-failures-first (then least recent), in batches, so resetting a key holding k failures requires first filling the table with keys holding at least k failures each. If every tracked key is blocked, all untracked keys share one overflow budget (max attempts x 10 failures per window): normal users keep working until it is spent, an attacker gets a fixed total number of guesses per window, and untracked keys are then blocked until it recovers. Residual risk: an attacker who sustains 10,000 blocked keys can exhaust the shared budget and briefly block new keys, and during that state per-account protection for untracked accounts is weaker than normal. This does not provide distributed enforcement; Redis remains the real fix. Replace with Redis before multi-worker production use.
- The per-address login limit (`LOGIN_IP_MAX_FAILED_ATTEMPTS`) is off by default. Trust forwarded client addresses only after setting `TRUSTED_PROXY_COUNT` to match the host's actual proxy chain.
- Production must use a strong unique `SECRET_KEY`, explicit non-local `CORS_ORIGINS`, and an HTTPS `MEDIA_PUBLIC_BASE_URL`; settings validation now fails startup when CORS/media origins are missing or unsafe. Configure these Render environment values before deployment.

## Product and UX gaps
- Workspace switching/creation, onboarding redirect, Content page, and Activity page have not been browser-tested.
- Workspace creation is capped per user by `MAX_WORKSPACES_PER_USER` (default 10), not yet part of the central plan catalog. Workspace rename/delete exist. Owner-only member role changes (admin/member) and member removal API endpoints have now been added, and expiring single-use email invitations can now be issued and accepted (migration `20261104_0025`). The acceptance page is implemented; a management UI for viewing/revoking pending invitations is still outstanding. Ownership transfer is not supported.
- Frontend has no automated test suite. Dashboard overview metrics are derived from fetched drafts, connected accounts, and workspace memberships (not sample data); the draft count is limited to the records returned by the drafts API.
- Profile PUT replaces the whole record (omitted optional fields are cleared); there is no PATCH, logo/brand-asset upload, or AI-generated brand context. Category changes currently require migrations; no category admin tooling exists.
- AI generation has only been tested with a fake provider. No live OpenAI call has been made; verify current provider API behavior and `OPENAI_MODEL` before enabling it. Output moderation/review policy remains to be designed.
- Usage limits remain placeholders/code-edited and concurrent requests may slightly overshoot. Billing now has customer checkout, Paystack webhook receipt/verification, subscription lifecycle controls, recurring authorization storage and customer-facing saved-authorization revocation (Increments 12–21). Automatic renewals remain disabled; customer OTP/3DS completion, renewal notifications, safe bounded retries, refunds/disputes, PostgreSQL, live Paystack/Google Pay and frontend build/browser QA remain outstanding. Increment 15 adds a scheduled reconciliation CLI and platform-admin run action, but the hosting cron/scheduler must still be configured; PostgreSQL concurrency and live Paystack behavior remain unverified. `PLATFORM_ADMIN_EMAILS` must be configured securely before using price administration.
- Drafts page in pages of 50 with a Load more button (API max 100 per request). Plain members delete only their own drafts. The UI's 402 quota handling is basic.
- Activity logging covers draft, business-profile, workspace creation, product/service CRUD and primary designation changes, social-account connection/disconnection, and Facebook publishing/scheduling. Registration, successful sign-ins and AI generations are now logged (Increment 32; failed sign-ins are not). The activity page has a category filter. There is no retention policy, export, or text search. Same-second ordering is not guaranteed on SQLite; PostgreSQL timestamps provide finer precision.

## TikTok publishing validation gaps

- TikTok Direct Post has not yet been exercised against a live developer app; app product setup, `video.publish` approval, sandbox testing and audit are external prerequisites.
- The unaudited client is private-only (`SELF_ONLY`) by backend enforcement.
- Upload status is automatically polled by the open publishing page; no server-side background poller or upload-session recovery exists yet. If the browser upload fails, the user must currently start a new upload session.
- TikTok access-token refresh/rotation is now attempted server-side when a request detects a token nearing expiry. Live refresh behavior still requires testing against TikTok credentials.
- Frontend install/build/browser validation remains outstanding because dependency installation timed out in the build environment.


## YouTube OAuth and publishing gaps
- Google OAuth connection and YouTube resumable upload/publishing workflows are implemented in code but have not been live-tested. Configure a Google Cloud Web OAuth client, enable YouTube Data API v3, and register the exact HTTPS callback URI before testing.
- OAuth currently identifies the authorized Google account; explicit channel selection/identity verification and browser-closure upload recovery are not implemented. Processing status is checked by the active page/on demand, not by a background worker.
- Google refresh-token behavior and provider revocation have not been live-tested.


## Facebook Page OAuth and calendar gaps
- Facebook Page OAuth, cursor-based Page discovery, encrypted Page tokens, and text/link publishing are implemented in code but have not been live-tested against Meta. Only Pages with the `CREATE_CONTENT` task are accepted.
- Facebook native scheduled posts and shared scheduled-post records are shown in the calendar. The calendar has month, week, and 30-day agenda views, plus TikTok/YouTube upload history.
- Immediate Facebook posts use `created_at` as their calendar timestamp because `scheduled_at` is null.
- Live Meta verification, Instagram media publishing, TikTok/YouTube shared scheduling, provider-side cancellation/rescheduling, and publishing-history recovery remain outstanding.

## Hybrid Brand Intelligence gaps
- Social post ingestion/sync, latest-20 retrieval, normalized source observations, provenance/confidence records, AI analysis, conflict detection, and owner/admin review/approval are not implemented. The current social accounts page must not imply that automatic brand analysis is already active.

## Shared scheduling — first slice limitations
- The durable scheduler supports Facebook Page text/link posts and Instagram professional-account single-image photo posts. Instagram requires a public HTTPS media URL and the `instagram_business_content_publish` scope; carousels, Reels, Stories, and video scheduling are not included. TikTok and YouTube remain outside the shared scheduler until their background media-transfer workflows are implemented.
- The dispatcher must be run periodically (`python -m app.modules.posting.dispatcher`) by an external process. Processing leases and exponential retry backoff are implemented, but no managed worker, cron service, Redis queue, or deployment process supervisor has been configured yet.
- Retry attempts are bounded to three. Retry delay/backoff, dead-letter administration, stale `processing` recovery after process crashes, and guaranteed exactly-once provider delivery are not implemented. Provider APIs do not generally provide an idempotency guarantee for this operation, so a crash after provider acceptance but before database commit can still require manual reconciliation.
- Schedule creation is now owner/admin-only; scheduling by an approver is the explicit approval boundary. There is not yet a required `draft_id` relationship tying a scheduled record to a previously approved draft. Verify datetime-local timezone conversion and full flow in a browser before production use.

## Durable media storage foundation (2026-11-02)
- Organization-scoped video asset upload and expiring signed delivery URLs are implemented as the first TikTok background-media foundation. Configure `MEDIA_STORAGE_DIR` on a persistent volume and `MEDIA_PUBLIC_BASE_URL` to the public HTTPS API origin before enabling provider-side URL fetches.
- The initial storage adapter writes to a local filesystem volume. It is suitable only when the deployment guarantees persistent shared storage between API and worker; object-storage integration, malware scanning, quotas, cleanup/retention, resumable/chunked upload, and worker orchestration remain outstanding.
- TikTok scheduled publishing is not enabled by this slice. The signed URL is a media-delivery primitive, not proof of TikTok URL-ownership verification or a completed provider upload.

## TikTok background transfer increment (2026-11-02)
- A tested server-side chunk-transfer helper now sends an existing local media file to a TikTok Direct Post `FILE_UPLOAD` session. It validates HTTPS and the exact `open-upload.tiktokapis.com` host, disables redirects, and sends byte-range headers for each chunk.
- This helper is not yet wired into scheduled-post dispatch. The worker must initialize a fresh TikTok Direct Post session at execution time, then transfer the asset and poll the publish status. TikTok states upload URLs expire after one hour; do not persist and reuse them as scheduled-job state.
- Current tests use mocked HTTP transport only. Live upload behavior, large-file/chunk boundary behavior against TikTok, PostgreSQL, and production worker supervision remain unverified.


## Remediation completed — 2026-11-04
- Tailwind CSS v4 dependency and PostCSS plugin configuration added; frontend build still requires dependency installation and verification.
- Render Docker build context corrected to `./backend`, matching Dockerfile COPY source paths. Actual hosted image build remains unverified.
- Production CORS and public media URL settings added to Render configuration; startup now validates these values.
- Direct schedule creation restricted to owners/admins. This prevents ordinary members from bypassing the approval boundary, but does not yet bind the scheduled content to an approved draft record.
- TikTok media upload now rejects files smaller than 5 MiB before persisting the asset.


## 2026-11-04 — Remaining YouTube upload recovery

- Added `app.modules.posting.youtube_worker` to independently poll durable YouTube video IDs after browser upload completion, so processing status no longer depends on a user keeping the status page open.
- This does not resume an interrupted browser-to-YouTube transfer when no video ID has been confirmed. The encrypted resumable session URL remains available in the job record, but browser/session recovery still needs a dedicated workflow.
- The poller is a separately invoked worker command; production scheduling/supervision and live YouTube verification remain outstanding.
- Scheduler leases now use an owner UUID, expiry timestamp, and a 30-second independent-session heartbeat (migration `20261104_0022`). Heartbeat ownership is conditional and stale workers are prevented from finalizing database state after losing their token. PostgreSQL multi-worker contention and provider-call interruption scenarios still require integration testing; this does not create provider-side idempotency.

## Scheduler ambiguous-outcome handling (2026-11-04)
- Facebook publish transport timeouts and HTTP 5xx responses are treated as uncertain outcomes after the POST begins. The dispatcher marks these jobs failed and asks an operator to verify the provider account before creating a replacement; it deliberately does not blindly retry and risk duplicate publication.
- Regression tests cover both timeout and 503 cases for Facebook and, for Instagram, failures at the `media_publish` step (ambiguous, not retried) versus failures creating the container or a 4xx rejection (safe, retried). The Instagram tests have not been executed yet. This is not exactly-once delivery: an operator must reconcile uncertain outcomes, and no provider idempotency key or automatic remote-post lookup is currently available.
- Verification in this increment: the focused ambiguity and rate-limit tests passed (6); the complete scheduling test module passed (12). The full backend suite did not finish within the execution limit; PostgreSQL and live-provider behavior remain unverified.

## Production rate-limit deployment requirement (2026-11-04)
- Production startup now requires a valid `REDIS_URL`; the bounded in-memory limiter remains available only outside production. This prevents an accidental multi-worker deployment from silently using per-process counters.
- `/ready` now pings Redis when configured. A Redis outage makes readiness return 503 so an orchestrator can keep the instance out of service. `/health` remains a process-liveness check and does not depend on Redis or PostgreSQL.
- Live Redis connectivity and production deployment configuration still need verification. Configure a managed Redis service and ensure TLS (`rediss://`) is used where supported.

## Scheduler: gaps found in review (2026-11-04)
- An uncertain outcome is stored as plain `failed` with a message. A brief provider outage after a post was NOT accepted looks identical to a post that may be live, so operators must check the account manually; a dedicated status plus a remote-post lookup would remove that ambiguity.
- If a worker loses its lease after the provider call succeeds, it logs an error and does not record the post. A later worker can then publish again, so duplicate posts remain possible in that narrow case until provider-side idempotency or reconciliation exists.
- No `package-lock.json` exists, so frontend installs are not reproducible and the frontend build is unverified.
- The status document's earlier "190 passed" figure predates the limiter and scheduler test changes; re-run the whole backend suite and update the figure from that run.

## Observations from the 2026-11-04 code review (not changed)
- Login throttling is keyed by `email|client IP` and the per-IP limiter is off by default, so an attacker rotating IP addresses gets a fresh set of attempts per address for the same account. Enable `LOGIN_IP_MAX_FAILED_ATTEMPTS` and set `TRUSTED_PROXY_COUNT` correctly behind a proxy; Redis-backed limiting remains the real fix.
- All uploaded media must be at least 5 MiB because of the TikTok chunked-upload method, even when the video is only meant for another provider.
- Signed media URLs and JWTs share `SECRET_KEY`. The signed message formats differ, so there is no known collision, but a separate media-signing key would be cleaner.
- OAuth `state` rows are marked consumed with a read-then-write rather than a conditional update, so two simultaneous callbacks with the same state could both pass. The one-time provider authorization code limits the impact.
- `record_usage` runs after the scheduled post is committed, and the quota check precedes creation, so concurrent requests can slightly exceed a plan quota.
- Password reset requests are throttled per email, so someone can keep a victim's reset requests exhausted (3 per hour) by spamming their address.

## Follow-up code review — 2026-11-04
- Facebook/Instagram scheduled publishing now fails closed on ambiguous post-request outcomes including malformed provider response data, missing post IDs, and local SQLAlchemy persistence errors. Explicit provider 4xx responses remain retry-safe/definitive rejections. This reduces duplicate risk but does not provide provider-side idempotency or reconciliation.
- Focused backend tests passed (86); the full suite, PostgreSQL concurrency, frontend lint/build, browser QA, and live provider verification remain outstanding. See `review-2026-11-04.md`.



## Stage-one review and social sign-in — 2026-11-04 (third pass)
- Added WhatsApp one-time-code sign-in, `/auth/providers`, optional email (`users.email` nullable) and `users.has_password` (migration `20261104_0024`). New backend tests (`test_google_login.py`, `test_whatsapp_login.py`) were written but **not run** (no dependencies or network in the authoring environment). Run the full suite and `alembic upgrade head` on SQLite and PostgreSQL before relying on this.
- WhatsApp delivery has never been exercised against the real Cloud API; it needs an approved Authentication template (see `whatsapp-sign-in.md`).
- Google sign-in deliberately does not link to a password-registered account whose email is unverified (pre-hijacking protection). The account owner can now verify via the email link and then link Google on a later sign-in.
- WhatsApp accounts have no email and no password: no password reset, no way to add an email or link a number to an existing account yet.
- The "complete your business profile" prompt (banner + one-time pop-up) replaces the old forced redirect to `/onboarding`; it is non-blocking and shown to owners/admins only. Frontend lint/build/browser behavior of these changes is unverified (`tsc` syntax check only).


## Workspace invitations increment — 2026-11-04
- Added migration `20261104_0025` and an organization invitation model. Invitation tokens are generated with a cryptographically secure random generator; only SHA-256 token hashes are stored. Tokens expire after seven days and are single-use.
- Owners and admins can invite email addresses; admins may invite members only, while only owners may invite admins. Acceptance requires an authenticated account whose email exactly matches the invited address.
- Added a frontend invitation acceptance page and post-login/registration local `next` redirect support. SMTP delivery is attempted through the existing mail integration; configure SMTP to deliver messages.
- Added backend regression tests for successful acceptance, email mismatch, replay rejection, and admin role restrictions. Focused organization tests pass on SQLite (18 passed). Full suite, Alembic migration execution, frontend lint/build, and browser/email delivery remain to be verified.

## 2026-11-04 follow-up status
- Workspace invitation management UI and list/revoke API are now implemented. Email verification is now implemented; invitation acceptance still requires the matching account email, not a verified email claim.
- `REDIS_URL` enables a shared Redis fixed-window limiter for authentication, password-reset, WhatsApp, and AI generation abuse guards. Without it, the existing bounded in-memory limiter is used. Configure Redis and validate connection/expiry behavior before multi-worker production deployment.
- `/api/v1/billing/plans` and `/api/v1/billing/readiness` are informational only. Prices are placeholders; checkout and webhooks are disabled. No subscription is sold or activated by these endpoints.
- Hybrid Brand Intelligence is not implemented. Do not claim social post sync or AI-derived brand facts are available.


## Brand Intelligence provider sync update — 2026-11-04
- Manual-triggered latest-20 post/video retrieval is implemented for Instagram, Facebook Pages, and TikTok. TikTok requires the newly requested `video.list` OAuth scope; already-connected TikTok accounts must reconnect and grant it before sync will work. The sync path refreshes/rotates TikTok access tokens server-side when they are near expiry. TikTok app configuration/approval for this scope is external and has not been verified live.
- YouTube Brand Intelligence retrieval is not implemented. The current YouTube OAuth flow requests `youtube.upload` only; a read scope and channel identity/read adapter must be deliberately added before claiming YouTube sync support.
- Automatic scheduled/background synchronization, retry orchestration, provider token refresh verification, PostgreSQL 16 integration, and live provider verification remain outstanding.


## Brand Intelligence background synchronization — 2026-11-04 follow-up
- The Brand Intelligence frontend now submits durable sync jobs and displays the latest job states/results, but its frontend production build and browser workflow have not yet been verified in this environment.
- The worker currently runs as an in-process daemon thread in the FastAPI application. Multiple API replicas can therefore run multiple workers; job claiming uses a conditional state update, but PostgreSQL multi-worker contention and deployment shutdown/restart behavior need integration testing. A separately supervised worker process may be preferable for production.
- Automatic six-hour scheduling currently considers connected social accounts generally. Confirm unsupported providers and accounts lacking required read scopes fail safely and do not create excessive repeated failure jobs.
- Polling refreshes job history every five seconds while active work exists; this is bounded to the current page and stops when all displayed jobs are terminal.


## Paystack billing — Increment 8 update (2026-11-04)
- A signature-verification helper now supports modern timestamped `Paystack-Signature` (including multiple `v1` signatures and five-minute timestamp validation) and legacy `x-paystack-signature`. Focused tests pass; see `docs/paystack-billing.md`.
- This is not a live billing integration: there is no webhook endpoint, transaction/subscription persistence, server-side initialize/verify flow, idempotent event processing, lifecycle handling, billing UI, or plan activation. Checkout/webhooks remain disabled. Plan prices are placeholders and require owner approval.
- Do not mark a subscription paid from a browser redirect or webhook alone. The next billing increment must persist transactions, verify each transaction server-to-server, validate amount/currency/customer/reference, and process webhook events idempotently before changing organization plans.

## Billing / Paystack status after Increment 9

- Paystack transaction retrieval and expected-value comparison helpers now exist in `app/integrations/payments/paystack_transactions.py`; tests use mocked HTTP responses only.
- The helpers are not wired into a checkout return endpoint or webhook processor. No transaction/subscription records exist yet, and no organization plan is activated from payment events.
- Owner-approved prices, currency/interval/tax/refund/cancellation policy are still required. Keep checkout and webhooks disabled until durable pending-transaction records, idempotency, webhook event persistence, amount/currency/customer validation, activity logging, and live provider tests are implemented.

### Paystack billing — outstanding after Increment 10

- Payment/subscription/webhook receipt tables now exist in migration `20261104_0029`, but no application service or endpoint writes them yet.
- Plan prices and billing policy are still unapproved; checkout must remain disabled.
- Webhook event-key construction and idempotent processing are not yet implemented; the unique `event_key` column is only the database guardrail.
- No verified-payment-to-subscription activation workflow or subscription lifecycle handling exists yet.
- PostgreSQL 16 migration verification and live Paystack test-mode verification remain outstanding.


## Billing and payment provider gaps — Increment 11
- The database price catalog is seeded by migration `20261104_0030`; apply migrations before expecting the public plan endpoint to show prices. SQLite tests do not run Alembic seed migrations automatically.
- Platform price editing is currently API-only (`GET/PUT /api/v1/billing/admin/prices`). The platform-admin frontend page exists at `/platform/billing-prices` but has not been browser-tested. Configure `PLATFORM_ADMIN_EMAILS` as a comma-separated allowlist of verified platform-owner emails.
- Paystack hosted-checkout adapter is a tested primitive, not yet wired to a customer checkout endpoint. Checkout and webhooks deliberately remain disabled until transaction persistence/orchestration and idempotent verified fulfillment are implemented.
- Google Pay is surfaced by Paystack Checkout when the merchant enables Google Pay and Card channels and account/customer eligibility is met. Actual merchant enablement, cross-border payments, recurring authorization and production checkout have not been tested.
- PayPal and Flutterwave are catalogued as future providers only; no credentials, API adapters, webhooks or checkout support are present.
- AI provider/model price tracking and cost alerts are not implemented. Customer subscription prices will not be changed automatically from provider price changes.


## Billing issues after Increment 12

- Live Paystack test-mode and production verification has not been performed. Checkout should remain disabled in production until merchant credentials, webhook URL/signing secret, test transactions and PostgreSQL checks are confirmed.
- Google Pay is not a standalone integration. It is shown by Paystack Checkout only when the merchant and customer/device/card are eligible; this has not been tested against the owner's account.
- Billing currently uses one-time charges. Automatic recurring renewals, cancellation, refunds, disputes/chargebacks, failed-payment grace periods, invoices/receipts and settlement reconciliation are not implemented. Increment 15 adds pending-payment reconciliation via CLI and platform-admin action; the hosting scheduler is not yet configured.
- A webhook event left in `processing` after an abrupt process crash can be manually retried by a platform owner after ten minutes (Increment 14). Increment 15 reconciles old pending payment attempts; it does not yet automatically reconcile stale webhook receipts themselves.
- Concurrent webhook/browser verification must be stress-tested on PostgreSQL; SQLite does not prove row-lock/idempotency behavior.
- Frontend dependency installation, lint, typecheck, production build and browser/mobile QA remain outstanding.
- A platform-wide customer account console now exists at `/platform` (Increment 13). It supports global customer search, inspection, user-level suspension/reactivation, payment diagnostics and audit history. Organization-wide suspension, customer deletion, impersonation and direct subscription editing are not implemented.
- AI provider/model cost tracking and cost-change alerts are not implemented. Customer subscription prices are intentionally not auto-increased.

## Platform administration / billing operations (Increment 13)

- The platform admin dashboard is restricted by the verified-email `PLATFORM_ADMIN_EMAILS` allowlist. Configure this before expecting `/platform` to appear.
- Customer suspension is user-level: it blocks authentication and invalidates all access tokens via `token_version`. It does not yet provide organization-wide suspension or a customer data deletion workflow.
- Payment operations show diagnostics and allow manual retry of failed Paystack `charge.success` webhook receipts (Increment 14). They do not issue refunds, cancel provider subscriptions, or automatically reconcile settlement reports.
- Paystack test/live mode is inferred from configured key prefixes only. It does not prove the keys work or that the merchant has Google Pay/international payments enabled.
- Live Paystack test-mode verification must be performed against the deployed callback URL and webhook URL using merchant test credentials. Never put secret keys in frontend environment variables or commit them.
- PostgreSQL 16 and full frontend build/browser tests remain outstanding.

## Increment 14 — billing recovery status (2026-11-04)

- [x] Added manual platform-owner retry for failed Paystack `charge.success` webhook receipts.
- [x] Added stale `processing` receipt retry guard (only after ten minutes) and rejection of recent in-flight receipts.
- [x] Recovery re-verifies the transaction directly with Paystack and uses the shared idempotent subscription fulfillment service.
- [x] Added platform audit records for retry success/failure/rejection and a dashboard retry action for failed charge-success events.
- [x] Scheduled pending-payment reconciliation code and CLI entry point added in Increment 15; configure hosting cron to run it every 5–10 minutes. [ ] Automated stale webhook-receipt recovery remains outstanding.
- [ ] Live Paystack test-mode behavior, PostgreSQL row-lock/concurrency semantics, and real webhook redelivery remain unverified.


## Billing lifecycle gaps after Increment 16 — 2026-11-04

- [x] Customer owner can schedule cancellation at the paid period end and reverse it before the boundary.
- [x] Billing UI displays recent payment attempts and cancellation/grace state.
- [x] Lifecycle CLI transitions due subscriptions to cancelled, past_due or expired and downgrades organization plans at the correct boundary.
- [ ] Hosting scheduler must be configured for `python -m app.jobs.process_subscription_lifecycle` (15–60 minute cadence); code presence does not mean it is running.
- [ ] Automatic recurring payment collection is not implemented; customers must initiate renewal checkout.
- [ ] Renewal reminder emails/SMS, refunds, disputes/chargebacks, downloadable invoices/receipts and tax handling remain outstanding.
- [ ] `BILLING_GRACE_PERIOD_DAYS` defaults to 3 days; owner should confirm this policy before public launch.
- [ ] Frontend dependencies/build/browser/mobile QA, PostgreSQL 16 concurrency testing, and live Paystack/Google Pay verification remain outstanding.


- Increment 17 adds the Paystack `charge_authorization` adapter primitive. Increment 18 adds optional consent capture and encrypted storage of verified reusable authorizations. Automatic renewals are still not active: durable renewal attempts, scheduled charge execution, recurring-debit server verification/fulfillment, 3DS challenge handling, bounded retries, notices, customer authorization revocation, and live test-mode validation remain outstanding. Do not enable automatic recurring billing until those controls are complete. Paystack may return a paused/3DS challenge response that requires customer interaction.
- `BILLING_AUTHORIZATION_ENCRYPTION_KEY` must be configured with a valid Fernet key before any reusable authorization can be stored. Without it, initial payment fulfillment continues but reusable authorization storage is skipped. Key loss prevents decryption; key rotation needs a controlled process.
- Migration `20261104_0034` must be applied before deploying Increment 18. PostgreSQL 16 migration and locking behavior remain unverified.


## Billing renewals — Increment 19 (2026-11-04)

- A durable `subscription_renewal_attempts` table now enforces one attempt per subscription and paid-period boundary (`20261104_0035`).
- The scheduled CLI `python -m app.jobs.process_subscription_renewals` is guarded by `BILLING_RENEWALS_ENABLED`, default `false`; do not enable it yet.
- The worker requires explicit consent, reusable Paystack authorization, encrypted authorization storage and the original checkout email. It uses server-side transaction verification before extending a subscription.
- Each period is charged at most once. A timeout/ambiguous response is reconciled by verification only; it is never charged again for the same period. Paystack pending/OTP/ongoing results are marked `needs_action` and are not retried.
- Still missing before activation: customer-facing 3DS/action completion, notices before first automatic charge and renewals, customer self-service revocation, bounded retry policy, operational alerting/support workflow, live Paystack test-mode validation, and PostgreSQL/multi-worker contention tests.
- Do not describe automatic renewal as production-ready or set `BILLING_RENEWALS_ENABLED=true` until these gaps are closed.


## Platform admin top customer leaderboard — Increment 20 (2026-11-04)

- `/platform` now shows a top-10 lifetime successful-payment leaderboard. It ranks by payments initiated by each user (`initiated_by_user_id`), not organization-wide revenue attributed to every workspace member.
- NGN and USD have separate rankings and a currency selector because no approved FX source/conversion policy exists. The admin can sort highest spend first or lowest spend first.
- Only transactions with `status=paid` are counted. Failed, pending and unattributed/deleted-user transactions are not included. Refunds/chargebacks are not yet implemented, so future refund support must update the net-spend definition.
- Frontend build/browser QA and PostgreSQL 16 verification remain outstanding.


### Billing — current Increment 21 limitations
- The billing page now displays whether a reusable Paystack authorization is stored and its safe card display metadata; only the workspace owner can deactivate it. The API clears local encrypted authorization only after Paystack confirms deactivation.
- Increment 22 adds the Paystack-hosted OTP/3DS challenge handoff and server-side verification return path. Real issuer challenge behavior and callback routing remain unverified. Renewal attempts requiring customer action must not be retried automatically.
- Increment 23 implemented renewal email notices; Increment 24 implemented verification-only recovery for `verification_pending` and stale `processing` attempts. There is deliberately no automatic re-charge retry for a declined, ambiguous or customer-action attempt. A future provider-approved retry policy must define retryable decline codes, limits, timing and idempotency before any same-period re-charge is considered. Live Paystack test-mode validation, operational alerting, PostgreSQL concurrency, actual issuer challenges and scheduler supervision remain outstanding. Keep `BILLING_RENEWALS_ENABLED=false`.


## Billing notices and automatic-renewal gate — Increment 23

- [x] Durable outbox and idempotent enqueueing for activation, advance reminder, customer-action and failed-payment notices.
- [x] Automatic renewal is blocked per subscription until its one-time activation notice is successfully handed to SMTP.
- [x] SMTP retry/backoff and stale-send lease recovery implemented.
- [ ] Configure and verify real SMTP credentials/deliverability. The current tests mock SMTP; no real message was sent.
- [ ] Schedule `python -m app.jobs.process_billing_notifications` daily or every few hours and verify all eligible activation notices are delivered before considering renewal activation.
- [ ] SMTP is at-least-once: a worker crash after SMTP accepts a message but before the database records it as sent may produce a duplicate on recovery.
- [ ] `BILLING_RENEWALS_ENABLED` remains false. Live Paystack test mode, actual issuer OTP/3DS, PostgreSQL 16 concurrency and production scheduler supervision remain outstanding.


## Interrupted renewal recovery — Increment 24

- [x] Added bounded verification-only recovery for stale `processing` and `verification_pending` renewal attempts.
- [x] Confirmed success uses the existing trusted fulfillment service; confirmed decline is marked failed and queues the existing customer notice.
- [x] Recovery never calls `charge_authorization`, creates a new payment reference, or automatically retries a charge.
- [ ] Schedule `python -m app.jobs.reconcile_subscription_renewals` every 5–10 minutes and observe operational outcomes.
- [ ] Validate provider verification and database row-lock behavior on PostgreSQL 16 and live Paystack test mode.
- [ ] Define operational alerts for long-lived `verification_pending`, `needs_action`, and terminally failed notifications.
- [ ] Keep `BILLING_RENEWALS_ENABLED=false` until all live provider, SMTP, PostgreSQL, challenge and scheduler checks are approved.


## Increment 25 — remaining operational verification (2026-11-05)

- [x] Implemented a narrow Paystack-directed retry path for explicit regulator wait responses; maximum one retry per billing period.
- [x] Added a unified five-minute billing maintenance runner and Render cron blueprint with structured output and non-zero exit on infrastructure failure.
- [x] Added DB readiness and opt-in SMTP smoke-test CLI.
- [ ] Deploy/confirm Render cron service and configure failure/missing-run alerts. This cannot be verified from the local repository.
- [ ] Configure real SMTP credentials, run the smoke test to a controlled inbox, and confirm delivery/spam handling.
- [ ] Run migrations and concurrency tests against PostgreSQL 16; SQLite tests are not a substitute.
- [ ] Verify Paystack test-mode regulator retry, same-reference behavior, and all other charge outcomes with the merchant account. Paystack documentation is not separate merchant approval.
- [ ] Frontend dependency installation, lint/typecheck/build and browser/mobile QA remain owner-side/deployment-environment checks.
- Keep both billing feature flags false until these checks are complete.


## Increment 26 — verification baseline (2026-11-05)

- Backend test files were split into two deterministic groups to fit the available execution window. Results were 178 passed and 183 passed/3 skipped, for **361 passed and 3 skipped** overall. The skipped tests are PostgreSQL-gated.
- The combined one-process suite exceeded the available execution window; partitioned execution completed successfully. Do not describe this as one uninterrupted full-suite run.
- Frontend package-lock generation, lint, build, TypeScript and browser QA remain blocked by absent dependencies and unavailable npm registry access.
- PostgreSQL 16, live social providers, live Paystack, real SMTP, deployed scheduler and production configuration remain unverified.
- Increment 30 additions (invitation resend, `last_sent_at` migration `20261105_0040`, `?method=rules` brand analysis, Vitest suite) were verified only by compile checks and pure-logic tests; run the backend suite, `alembic upgrade head`/`alembic check`, and `npm install && npm test` before relying on them.


## Pre-deployment blockers confirmed — 2026-11-07

- The current repository archive does not contain `frontend/package-lock.json`; reproducible `npm ci`, lint, typecheck, Next.js production build, and browser/mobile QA have not been demonstrated. Generate the lockfile using Node 22/npm 10 in a network-enabled environment; do not hand-author it.
- The current repository archive does not contain a `.github/workflows` CI pipeline, despite historical project-status notes describing a workflow. Reconcile this before release and ensure backend/PostgreSQL and frontend checks run on every pull request.
- PostgreSQL 16 migration and application integration/concurrency behavior have not been verified in this environment. SQLite-only test evidence is not a substitute.
- SMTP inbox delivery, live Meta/TikTok/YouTube/Google/WhatsApp authentication and publishing, live Paystack test-mode checkout/webhooks, Render cron execution, and production deployment/rollback remain unverified.
- The root `Dockerfile` is demo-only. Production API deployment must use `backend/Dockerfile` / `backend/render.yaml`; do not use the root demo Dockerfile for a production service.
- Production frontend builds now require `NEXT_PUBLIC_API_BASE_URL` to be set to the public HTTPS API origin. Configure this in the frontend hosting provider before triggering a production build.

## Demo readiness (Increment 54)
- Customer and platform-owner demo identities are now separate (`DEMO_EMAIL` and `DEMO_ADMIN_EMAIL`). Never put the customer demo email in `PLATFORM_ADMIN_EMAILS`. Demo admin one-click access is intentionally public only on isolated demo deployments; never enable `DEMO_MODE` in production or point it at PostgreSQL/customer data.
- Full frontend build/browser QA and a dependency-complete backend CI run remain outstanding. Some existing platform-admin/billing tests still use owner fixtures without the MFA now required by the security policy; update those fixtures rather than weakening MFA.
