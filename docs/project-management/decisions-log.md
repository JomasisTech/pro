# Architecture and Technical Decisions

## D-001 — Modular monolith
**Decision:** Keep the backend in one FastAPI application, organized by business modules as they become necessary.  
**Reason:** Lower operational complexity while preserving clear module boundaries.

## D-002 — PostgreSQL from the beginning
**Decision:** Use PostgreSQL as the intended database and SQLAlchemy 2.x for data access.  
**Reason:** Strong relational integrity and a suitable foundation for organization-scoped SaaS data.

## D-003 — Environment-based configuration
**Decision:** Read configuration from environment variables and a local `.env` file for development.  
**Reason:** Secrets and environment-specific settings must not be hardcoded or committed.

## D-004 — Separate liveness and readiness
**Decision:** `/health` checks whether the API process responds; `/ready` checks database connectivity.  
**Reason:** A running application and a database-ready application are different operational states.

## D-005 — Frontend/backend deployment separation
**Decision:** Prepare the Next.js frontend for Vercel and the FastAPI backend for a Python web host such as Render or Railway.  
**Reason:** These services have different runtime needs. Final host selection will depend on pricing, database, background worker, and deployment requirements.

## D-006 — Foundation-first, then end-to-end vertical slices
**Decision:** Verify the core foundation first, establish the frontend shell early, then implement each capability across backend, frontend, and integration tests before moving to the next capability. Do not finish the entire backend roadmap first, and do not develop all layers in uncontrolled parallel.  
**Reason:** This balances architectural stability with early UI feedback, reduces late API/UI mismatches, and makes progress verifiable in working user journeys. Security foundations must precede dependent features.  
**Verification rule:** Unit tests and SQLite/mocked tests do not substitute for real PostgreSQL, external-provider, or deployment verification.

## D-007 — Preserve the full target structure separately from the active MVP
**Decision:** Keep the long-term platform architecture and target tree in `docs/full-project-blueprint.md`; use project status to determine what is active now. Do not generate all future folders/modules up front.  
**Reason:** Future AI assistants need the destination and product roadmap without mistaking planned work for existing implementation or expanding scope prematurely.  
**Current scope:** Foundation verification, then Product 01 Social Media Automation. Products 02–07 remain future roadmap.

## D-008 — Argon2id for password hashing
**Decision:** Hash new passwords with Argon2id via `argon2-cffi` (library-default parameters), as required by the master prompt. Legacy PBKDF2 hashes still verify and are upgraded to Argon2id on the user's next successful login.  
**Reason:** Argon2id is memory-hard and is OWASP's first-choice algorithm; PBKDF2 was an interim implementation.  
**Verification status:** Code compiles; new tests in `backend/tests/test_password_hashing.py` have NOT been run yet (no network to install `argon2-cffi` in the authoring environment). Run `pip install -e ".[dev]" && pytest -q`.

## D-009 — Backend tenant authorization returns 404 for non-members
**Decision:** Organization-scoped routes resolve the caller's membership first; non-members receive `404`, members lacking a required role receive `403`.  
**Reason:** Prevents leaking which organizations exist and keeps one reusable enforcement point for future business endpoints.

## D-010 — Interim in-memory login rate limiter
**Decision:** Limit failed logins per email + client address with an in-process sliding window (5 failures, 15 minutes).  
**Reason:** Adds brute-force protection now without new infrastructure. Known limits are recorded in `known-issues.md`; replace with Redis when Redis is introduced.

## D-011 — Proxy-aware client address, optional per-address limit, startup secret guard
**Decision:** Resolve the client address from the end of `X-Forwarded-For` only when `TRUSTED_PROXY_COUNT` > 0; add an optional per-address failed-login limiter (off by default); run a dummy Argon2 check for unknown emails; refuse to start in production with a default or short `SECRET_KEY`.  
**Reason:** Closes the enumeration, spoofing, spraying, and account-lockout-by-others gaps recorded after D-010 without new infrastructure, and prevents deploying with a publicly known signing key.

## D-012 — One self-referencing category table; business profile as one row per organization
**Decision:** Store industries and subcategories in a single `industry_categories` table (`parent_id` null for industries), seeded by migration with deterministic UUIDs, served by `GET /categories`. Store the business profile in `business_profiles` with a unique `organization_id`, saved with PUT (full replacement), writable by owners/admins only.  
**Reason:** Meets "data-driven categories" without a second table or admin tool, keeps one profile per tenant enforced by a database constraint, and reuses the D-009 authorization dependencies.  
**Verification status:** Not yet run (see known issues).

## D-013 — Thin AI provider interface; stateless generation first
**Decision:** Business code uses an `AIProvider` protocol; OpenAI is called over plain HTTP with `httpx` (no SDK). Generation returns text without saving; drafts, approval, and UI are separate slices. A per-user hourly cap guards cost.  
**Reason:** Keeps providers swappable, avoids an extra dependency, and lets the prompt/tenant/limit behavior be tested without paid calls.

## D-014 — Central plan catalog and per-organization monthly usage events
**Decision:** All plan limits live in `app/core/plans.py`. Each organization has a `plan`; limited actions are recorded as `usage_events` and checked via `require_quota`. Only trusted backend code may change a plan.  
**Reason:** One place to change numbers, consistent enforcement across features, and a clean seam for Paystack billing later. Chosen over a database-backed catalog now to avoid building admin tooling prematurely.

## D-015 — Append-only activity log written in the same transaction
**Decision:** Record who did what in `activity_logs` via `record_activity`, committed together with the change; entries store an actor-name snapshot and an unconstrained entity id; readable only by owners/admins; no edit/delete endpoints.  
**Reason:** Gives teams accountability (master prompt: audit logging) and keeps history accurate after users or items are deleted. Atomic writes prevent changes without a log entry.


## D-016 — User-provided business facts are primary brand context
**Decision:** Onboarding explicitly asks for industry and niche, along with business description, products/services, audience, marketing goals, and brand preferences. Social post analysis is optional supplementary evidence; it must not silently override user-confirmed information. Conflicts are surfaced for user review.
**Reason:** New businesses and low-post accounts still need useful AI personalization, and social content may not fully represent the business.

## D-017 — Central business context read model
**Decision:** Keep organization-owned business profile fields as the editable source of truth and expose a tenant-scoped business-context endpoint that assembles user-provided facts and profile completeness for downstream AI features. Keep new fields nullable for backwards compatibility while the current onboarding UI requires industry and niche for new submissions.
**Reason:** AI modules need a consistent context contract without duplicating business-profile lookup and completeness logic. Social-derived context will be added separately with explicit provenance and confidence.


## D-018 — Structured products and profile confirmation
**Decision:** Keep a profile-level free-text offer summary for backwards compatibility, while introducing separate organization-owned product/service records. Require an explicit owner/admin confirmation for the essential business profile. Profile edits invalidate confirmation and create immutable snapshots; confirmations are separately recorded.
**Reason:** Structured offers are easier for AI and future campaigns to consume, while explicit review prevents inferred or stale business details from silently becoming approved facts.


## D-019 — Official OAuth integrations and evidence-backed brand intelligence
**Decision:** Connect social platforms only through official OAuth/API integrations. Keep social observations separate from user-provided business facts, preserve provenance and confidence, and require user review before promoting observations into the brand profile. Begin with provider-neutral connection/sync contracts, then deliver one provider adapter at a time according to actual app approval and scopes.
**Reason:** Platform permissions vary by provider and account type; OAuth consent does not imply access to every post, metric, or publishing feature. This prevents unsupported data claims, unsafe token handling, and silent changes to the user's business identity.

### D-019 — Never represent an unverified social connection as connected
- Status: Accepted
- Decision: Provider availability remains false until OAuth credentials, callback handling, requested scopes and token lifecycle are configured and tested. Browser clients never submit social access tokens directly. Only verified server-side OAuth callbacks may create connected-account records.
- Rationale: Prevent misleading connection states and reduce credential exposure.

### D-020 — Instagram Login and Facebook Page Login are distinct integrations

The first Meta integration uses Instagram Login for Instagram professional accounts and the `instagram_business_basic` permission. It must not imply that a Facebook Page is connected. Facebook Login for Business/Page discovery is a separate implementation with its own permissions, token handling and review requirements.

### D-021 — Encrypt social tokens independently

Provider credentials are encrypted at rest using `SOCIAL_TOKEN_ENCRYPTION_KEY`, separate from the application JWT signing secret. Tokens are never returned to frontend endpoints. Production configuration must fail closed when Meta credentials are partially configured.


## D-022 — One reusable video-script engine, platform-specific outputs
**Decision:** Generate scripts from the confirmed business context and adapt the production structure for TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, and long-form YouTube. Scripts include a hook, timestamped scenes, visual and audio direction, on-screen text, caption, title, description, hashtags, and recording notes. Save them as editable drafts.
**Reason:** A single business idea can be repurposed across destinations without losing each platform's format. Video scripts are useful even before automated video rendering or publishing is available.

## D-023 — Platform availability is not the same as platform support
**Decision:** TikTok and YouTube may appear in the provider directory and Video Script Studio, but their Connect/Publish actions remain disabled until official OAuth, scope approval, token lifecycle, media transfer, and publishing-status handling are implemented and verified.
**Reason:** Avoid implying that script generation means a platform account is connected or that video publishing is available.


## 2026-11-02 — Calendar UI without API expansion
The first calendar UX increment uses the existing authenticated `/calendar` feed and performs month/week/agenda presentation in the client. This avoids introducing a calendar dependency or database/API changes before the source data includes additional providers. The UI must clearly disclose that TikTok/YouTube jobs and cross-platform scheduling are not yet supported. Revisit server-side range queries and pagination when calendar volume/provider coverage grows.

## D-024 — Durable provider-neutral schedule records with capability-gated dispatch
**Decision:** Introduce one organization-scoped scheduled-post record and a database-backed dispatcher. The first adapter dispatches Facebook Page text/link posts only; other platforms are not accepted until their media-transfer and background-publishing requirements are implemented. The dispatcher claims work with an atomic queued-to-processing update and bounds retries.
**Reason:** Establish a reusable scheduling contract without pretending video providers can publish from the existing browser-only upload sessions. A database queue is sufficient for the first slice; Redis/Celery is deferred until operational scale and hosting requirements justify it.

## Decision: private durable media asset foundation
**Date:** 2026-11-02
**Decision:** Add organization-owned media asset records with private filesystem storage and short-lived HMAC-signed HTTPS delivery URLs as the first step toward background video publishing. Keep provider scheduling disabled until persistent shared storage/object storage, TikTok URL ownership verification, worker transfer, retries, and live provider tests are complete.
**Reason:** TikTok browser upload sessions expire and cannot serve as a durable scheduled-job source. A private stable source asset separates user upload from provider upload without exposing account tokens or public directory listings. Production deployments must mount persistent storage and configure the HTTPS public API origin.

## Decision: initialize TikTok upload sessions at dispatch time
**Date:** 2026-11-02
**Decision:** Keep TikTok's short-lived upload URL out of durable schedule records. The background worker will create a Direct Post session only when a scheduled item is due, then transfer the organization's stored media asset to the returned upload URL using sequential byte-range requests. The transfer helper validates the exact TikTok upload host and does not follow redirects.
**Reason:** TikTok documents a one-hour upload URL lifetime. Persisting a URL at schedule-creation time would make future scheduled posts unreliable and retaining provider session URLs would add unnecessary secret-like state to the database.


## 2026-11-02 — TikTok scheduled videos use stored media assets

TikTok scheduled video posts reference private organization-owned media assets. The worker creates the one-hour upload session only when the post becomes due, uploads the file server-side, stores the provider publish ID, and polls status on later runs. The existing browser-based Direct Post endpoint remains available and unchanged. Unaudited clients are restricted to `SELF_ONLY`.

## 2026-11-04 — Session revocation and password reset design
**Decision:** Keep stateless HS256 access tokens but add a `jti` per token and a per-user `token_version`. Logout inserts the `jti` into a `revoked_tokens` denylist; password change/reset and "sign out everywhere" bump `token_version`. Password reset uses random 256-bit one-time tokens stored only as SHA-256 hashes, delivered by email in a URL fragment, valid 30 minutes, single use, with the forgot-password endpoint answering identically for known and unknown emails. Email goes through a small standard-library SMTP helper that can later be replaced by a hosted provider.
**Reason:** Gives real logout and session invalidation without a full session-table/refresh-token redesign, which remains future work together with the cookie-session review. A fast hash is suitable for reset tokens because they are high-entropy random values, not user-chosen passwords.


## 2026-11-04 — YouTube processing polling is independent of browser sessions
**Decision:** Add a small database-backed polling worker for YouTube jobs with a verified `video_id`, separate from the browser upload flow. It checks YouTube processing status and persists `uploaded`, `processing`, `published`, or `failed` state.
**Reason:** A user closing the browser after upload completion must not stop server-side processing-status updates. Interrupted transfers without a verified video ID remain a separate recovery problem.

## 2026-11-04 — WhatsApp sign-in via one-time code; non-blocking profile prompt
- WhatsApp is not an OAuth provider, so sign-in uses a 6-digit code sent through a WhatsApp Authentication template. Accounts have no email/password (`email` nullable, `has_password=false`).
- Google never links to an unverified password-registered account (pre-hijacking); revisit with email verification.
- The forced redirect to `/onboarding` was replaced by a dismissible banner + one-time pop-up for owners/admins.


## D-025 — Paystack signature verification before payment processing
**Date:** 2026-11-04
**Decision:** Implement the Paystack webhook signature verifier as a provider integration helper before exposing a webhook route or granting paid access. Support the current timestamped `Paystack-Signature` format with a five-minute tolerance and secret-rotation signatures, plus legacy `x-paystack-signature` during migration. Verify the exact raw request bytes and use constant-time comparisons.
**Reason:** A webhook endpoint must authenticate the sender before parsing or acting on payment events. Signature validity alone does not prove that a transaction amount/currency is correct or that a subscription should be activated; those checks require persisted transaction state and server-side transaction verification. Checkout stays disabled until owner-approved pricing and those safeguards exist.

## D-026 — Verify Paystack transactions server-to-server before fulfillment
**Date:** 2026-11-04
**Decision:** Add a provider integration helper that retrieves a transaction from Paystack using the server-side secret key and a separate pure comparison helper for the expected reference, successful transaction status, amount in minor currency units, currency, and optional customer email. The helper does not activate subscriptions or change organization plans.
**Reason:** Browser callbacks and webhook notifications must not be treated as proof of payment. A later billing workflow must compare provider results with a pending transaction created from trusted server-side plan/pricing data, then apply idempotent fulfillment.

## 2026-11-04 — Increment 10 payment persistence schema

- Added durable payment transaction, subscription, and webhook receipt models plus Alembic migration `20261104_0029`.
- Payment and subscription records use non-active defaults; schema work alone cannot grant paid access.
- Webhook receipts store event metadata and a body digest rather than retaining raw payment payloads.
- Checkout and webhook endpoints remain disabled until prices/policies are approved and server-side verification, idempotent processing, activity logging, and PostgreSQL/live-provider tests are complete.


## D-027 — Provider-neutral payment integration and managed plan prices
**Date:** 2026-11-04
**Decision:** Use a provider-neutral payment contract/registry. Paystack is the first implemented provider; Google Pay is a Paystack checkout channel. PayPal and Flutterwave remain future adapters. Keep plan prices in a database catalog with integer minor units and an append-only change history, editable only by a platform-owner email allowlist. Seed NGN/USD Standard/Premium monthly and annual prices; annual prices equal ten monthly payments.
**Reason:** New payment providers should be addable without rewriting subscriptions or price logic. Manual, audited price changes are safer than automatically increasing customer prices when AI/provider costs change. Checkout remains disabled until signed/idempotent webhooks, server-side transaction verification and atomic subscription fulfillment are implemented.


## 2026-11-04 — Increment 12: customer billing vertical slice

- Approved initial NGN/USD Standard/Premium price catalogue from Increment 11 is now consumed by customer checkout. The browser never supplies the amount; checkout snapshots a server-selected price.
- Paystack is the only active processor. Google Pay is surfaced through Paystack Checkout where eligible. PayPal and Flutterwave remain future provider adapters and must not be represented as active.
- Subscription activation requires a server-to-server Paystack verification matching reference, amount, currency, customer email and successful status. A browser redirect alone is not proof.
- Customer billing is one-time charge per period for now. Automatic recurring renewal, cancellation, refunds/disputes and settlement reconciliation are deliberately deferred. Increment 15 adds pending-payment reconciliation, but does not enable auto-renewal. Do not imply auto-renewal is active.
- Price changes affect future checkouts only; existing subscription price snapshots remain unchanged. Customer price increases remain manually approved.
- The platform currently has workspace member administration and platform-owner billing-price administration, but no global customer account-management console.

## D-028 — Platform-wide administration uses verified platform-owner allowlist
**Date:** 2026-11-04
**Decision:** Keep platform administration separate from organization workspace roles. Gate all global customer and billing-operations endpoints using the existing verified-email `PLATFORM_ADMIN_EMAILS` allowlist. Account suspension increments the target user's token version to revoke existing sessions, and all global account-status changes write an append-only platform audit record.
**Reason:** Workspace owners/admins must never gain access to other customers' records. A simple allowlist fits the current early-stage owner-operated platform without introducing a new role hierarchy or privileged bootstrap flow. A future multi-operator admin role model can replace the allowlist when needed.

## 2026-11-04 — Increment 13 platform admin console

- Added `/platform` for global customer account operations, protected by the same verified `PLATFORM_ADMIN_EMAILS` allowlist as pricing administration.
- Customer suspension invalidates existing sessions through `token_version`; self-suspension and suspending another allowlisted platform administrator are blocked.
- Added separate append-only `platform_admin_audits` because global actions do not naturally belong to an organization activity stream.
- Payment operations are read-only diagnostics; key-prefix mode detection is not a provider connectivity check and must not be reported as live verification.

## 2026-11-04 — Increment 14: controlled Paystack webhook recovery

- Added a platform-owner-only manual retry endpoint for failed Paystack `charge.success` webhook receipts and stale `processing` receipts older than ten minutes.
- Recovery always performs a fresh server-to-server transaction lookup and reuses the existing trusted fulfillment service; webhook data alone never activates a plan.
- Recent processing receipts and non-charge-success events cannot be retried. Attempts/outcomes are recorded in the platform admin audit trail.
- The platform dashboard exposes a retry action for failed charge-success receipts. At the time of Increment 14 this was not an automatic reconciliation worker; Increment 15 subsequently adds scheduled pending-payment reconciliation.


## 2026-11-04 — Increment 15: bounded scheduled Paystack reconciliation
- Reconcile only pending Paystack payment attempts older than a configurable minimum age (default 10 minutes), in bounded batches.
- Always retrieve transaction status from Paystack and reuse the established expected-reference/amount/currency/email checks and idempotent fulfillment service. Never grant access from webhook payloads or browser redirects.
- Expose an authenticated platform-owner run action for operational use and a CLI entry point for hosting cron/scheduled jobs. Avoid starting an unmanaged in-process timer in each FastAPI replica.
- PayPal and Flutterwave remain skipped until their provider adapters exist.
- PostgreSQL concurrency and live provider verification remain deployment-stage requirements.


## 2026-11-04 — Increment 16 subscription lifecycle policy

- Cancellation is scheduled for the end of the already-paid period; no prorated refund is implied. The workspace retains paid access until the period boundary. The owner may reverse a scheduled cancellation before the boundary.
- If a paid period ends without a verified renewal and no cancellation was requested, the subscription enters `past_due` and retains the existing plan for a configurable grace period. Default is 3 days, configurable through backend-only `BILLING_GRACE_PERIOD_DAYS` (0–14). The owner must review this default before public launch.
- After the grace window, subscription becomes `expired` and organization plan becomes `free`. A requested period-end cancellation becomes `cancelled` and downgrades to `free` at the boundary without a grace period.
- This lifecycle processor does not charge customers. Automatic recurring payment collection remains a separate future implementation requiring verified provider authorization and live merchant testing.
- Customer billing history is visible to workspace members but contains only safe transaction metadata; no raw webhook payloads or provider secrets are exposed.


## 2026-11-04 — Increment 17 recurring billing safety boundary

- Decision: add the Paystack authorization-charge operation as a provider adapter primitive, but do not activate scheduled charging until explicit customer consent, encrypted reusable authorization storage, durable renewal attempts, verified fulfillment, 3DS handling, bounded retries, and customer notices are implemented.
- Rationale: Paystack requires that only `reusable: true` authorizations be charged and that the original authorization email be retained. A successful API charge-initiation response is not itself proof that the subscription period may be fulfilled. See the Paystack recurring-charges documentation linked in `docs/paystack-billing.md`.
- Future providers remain behind the existing provider registry; PayPal and Flutterwave remain future integrations.


## D-029 — Explicit recurring consent and encrypted authorization custody
**Date:** 2026-11-04
**Decision:** Recurring payment consent is optional and explicit at checkout. Unchecked purchases remain one-time payments. Store the consent timestamp, version and server-authored wording snapshot on the payment attempt. Persist a Paystack authorization only after server-side transaction verification confirms `authorization.reusable: true` and only when consent was recorded. Encrypt the authorization code with a dedicated backend-only Fernet key; retain the exact original checkout email and limited card display metadata, never PAN/CVV.
**Reason:** Payment completion does not imply permission for future off-session charges. Authorization custody must be separated from social OAuth credentials and unavailable for charging when encryption is not configured. Automatic charging remains disabled until renewal attempts, verification/fulfillment, 3DS handling, retries, notices and customer revocation are implemented and tested.


## D-030 — Durable, opt-in recurring renewal attempts
**Date:** 2026-11-04
**Decision:** Add a durable renewal-attempt ledger with a unique `(subscription_id, period_end)` constraint. A scheduler may initiate a Paystack authorization charge only when the feature flag is explicitly enabled, the subscription is due and not scheduled for cancellation, explicit recurring consent exists, and a reusable encrypted authorization plus its original email are present. Every initiated charge is verified server-to-server before subscription fulfillment. A period gets at most one charge initiation; ambiguous responses are verification-only, and customer-action responses are not automatically retried.
**Reason:** Off-session payment retries can accidentally double-charge customers if a timeout occurs after Paystack has accepted a request. A unique period key and no-repeat policy prioritize avoiding duplicate debits while customer-action UX and a provider-validated retry policy are still being completed. The feature flag defaults off; enabling it is a separate operational approval after test-mode and customer-notice requirements are met.


## D-031 — Currency-safe platform customer spending leaderboard
**Date:** 2026-11-04
**Decision:** Rank customers by lifetime successful payments they initiated (`PaymentTransaction.initiated_by_user_id`) using only `status=paid`. Show the top 10 in either descending or ascending order. NGN and USD must be ranked separately and explicitly selectable; do not sum or compare unlike currencies without an approved exchange-rate source and conversion timestamp policy.
**Reason:** The payer identity is the reliable user-level attribution currently persisted at checkout. Currency separation avoids misleading rankings, while paid-only aggregation excludes attempts that did not complete. If refunds/chargebacks are introduced, the leaderboard metric must be revisited to represent net collected spend.


## 2026-11-04 — Increment 21: customer-controlled Paystack authorization revocation
- Decision: customers must be able to see that a reusable payment authorization is stored and the workspace owner must be able to revoke it from the billing page. Revocation calls Paystack's documented `POST /customer/authorization/deactivate` endpoint.
- Safety: do not erase the local encrypted authorization or report success until Paystack confirms deactivation. If the provider request fails or is ambiguous, retain ciphertext and surface an error so the owner can retry/contact support.
- Privacy: the customer API exposes only a boolean saved-state and safe card metadata; never expose authorization code or ciphertext. Keep historical consent evidence after revocation.
- Scope: this does not enable recurring charges, finish OTP/3DS challenges, or introduce automatic retries. `BILLING_RENEWALS_ENABLED` remains false by default and must remain false until the remaining renewal safeguards and live tests are complete.


## 2026-11-04 — Paystack renewal challenge handoff (Increment 22)
- **Decision:** Persist only a Paystack-hosted challenge URL after a recurring charge returns `paused` / `authorization_url`; require HTTPS and the exact `checkout.paystack.com` hostname. Return the link only to workspace owners/admins. After the customer returns to `/billing`, re-verify the durable payment reference server-to-server before applying subscription fulfillment.
- **Reason:** A browser redirect is not proof of payment. The challenge URL must not become an open-redirect vector, and a paused authorization must not be retried as a new charge. Paystack documents redirecting customers to `authorization_url` and verifying the returned reference after authentication.


## D-032 — Transactional billing notification outbox and pre-charge notice gate
**Date:** 2026-11-04
**Decision:** Billing emails are queued in a durable database outbox with unique event keys, bounded SMTP retries and tenant/subscription linkage. A one-time automatic-renewal activation notice must be successfully handed to SMTP before the subscription's `recurring_billing_notice_sent_at` is set; the renewal worker excludes subscriptions without this timestamp. A new saved authorization resets the timestamp, and revocation clears it. Automatic renewals require both `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=true` and an SMTP host.
**Reason:** Explicit consent and reusable authorization alone do not satisfy the customer-notice requirement. The system must not silently charge customers before an advance notice has been delivered. The database gate protects each subscription even if an operator enables the global renewal flag prematurely. SMTP delivery is at-least-once because SMTP acceptance and the local database commit cannot be made atomic.


## D-033 — verification-only recovery for interrupted recurring charges
**Date:** 2026-11-04
**Decision:** Recover old `processing` and `verification_pending` renewal attempts only by verifying their existing Paystack transaction reference. Never issue a second authorization charge automatically for the same subscription period. A stale `processing` attempt older than ten minutes is conservatively reclassified as verification-pending before verification. A confirmed success uses the existing trusted fulfillment path; a confirmed decline is marked failed and queues the existing failure notice; provider outages or mismatches remain pending/attention-required.
**Reason:** A worker can crash after Paystack receives a charge but before the application persists its response. The application cannot safely infer whether a debit occurred. Reusing the existing reference for server-side verification recovers successful outcomes without duplicate charging. Provider-specific retry rules require documented retryable response codes and live validation; they are not assumed.


## D-034 — provider-directed renewal retry and one managed scheduler
**Date:** 2026-11-05
**Decision:** Permit at most one delayed retry for a recurring authorization charge only when Paystack explicitly returns its documented recurring-card regulator wait (`retry_by` or the explicit “cannot be fulfilled until X minutes” response). Persist the retry time and count, wait until the provider-specified time, re-check current subscription consent/authorization/period eligibility, and retain the existing local payment reference. Do not retry ambiguous network failures, generic declines, insufficient funds, OTP/3DS challenges, or unknown statuses. A second regulator restriction ends automatic retry.

Use one unified bounded billing maintenance runner scheduled every five minutes, rather than independently scheduled overlapping commands. It processes notices first, then verification-only reconciliation, provider-directed retries, guarded new renewals, and lifecycle transitions. Emit structured summaries and fail the process on infrastructure errors. Keep the Render cron flags for notifications and renewals false by default.

**Reason:** Paystack documents a regulator response that restricts repeated recurring-card attempts and indicates when another attempt may be allowed. A narrow, explicit provider-directed window is safer than inventing a generic retry policy. A single managed scheduler makes ordering and monitoring easier. This is not separate written approval for the BizPilotPro merchant account; live test-mode and merchant confirmation remain mandatory.


## D-035 — Pipeline-based lead generation with durable live progress
**Date:** 2026-11-05  
**Decision:** Capture the future lead-generation workflow as independently observable stages: request/target understanding, compliant business discovery, contact extraction/enrichment, normalization/deduplication, email quality checks, explainable lead qualification, customer review, optional AI outreach drafting, quality/compliance review, explicit approval, controlled sending, and performance analysis. The frontend must show real backend-confirmed progress for each stage, including counters, partial results where safe, waiting/approval states, and failures. Job and stage state must be durable and tenant-authorized; prefer replayable SSE with a snapshot endpoint and bounded polling fallback. Reuse/evaluate the existing Brand Intelligence sync-job pattern before introducing another job framework.

**AI design:** Do not require one model per stage. Use the configured provider for separate structured tasks where reasoning adds value, and deterministic services for normalization, deduplication, validation, authorization, suppression, idempotency, and delivery. Additional models require measured quality/cost benefit.

**Compliance and safety:** Use approved/licensed sources and preserve provenance; do not bypass access controls or fabricate/guess contact details. Public business contact information is not blanket permission for marketing. Product 04 must enforce the applicable consent/lawful-basis policy, suppression, unsubscribe, customer approval, and sending safeguards.

**Scope:** This records future Product 02, Product 04, Product 06, and cross-cutting job-progress requirements. It does not change the active scope: foundation hardening and Product 01 remain current until project status is explicitly updated.

**Reason:** The owner wants customers to see what the system is doing instead of waiting without feedback. Durable progress improves transparency, trust, recovery, and supportability while keeping the pipeline modular and avoiding unnecessary multi-agent complexity.


## D-036 — Guard destructive PostgreSQL integration tests and require a real frontend lockfile
**Date:** 2026-11-05  
**Decision:** PostgreSQL integration tests that call `Base.metadata.drop_all/create_all` must require an explicit `TEST_POSTGRES_ALLOW_DESTRUCTIVE=1` opt-in, a local test host, and a clearly named disposable database (`ci_db` or `test_*`). CI alone sets the opt-in for its isolated PostgreSQL 16 service. The frontend dependency lockfile must be generated by npm from the real manifest in a network-enabled Node 22/npm 10 environment; do not hand-author or fabricate it. After a reviewed lockfile is committed, CI should use `npm ci`.  
**Reason:** Prevent destructive integration tests from accidentally targeting production or an ordinary developer database, and make frontend installs reproducible without inventing dependency resolution data.

## 2026-11-05 — Dashboard visual direction and MVP scope

**Decision:** Align the authenticated home/dashboard with the supplied light-mode dashboard reference: a welcome hero, colored icon shortcut row, live operational metrics, connected social accounts, content creation callout, upcoming publication list, and recent drafts. Keep the dashboard within Product 01 Social Media Automation and use only data already returned by the current authenticated APIs. Do not add placeholder lead-management, email-marketing, or invented social-performance analytics panels. Use purple/blue as the core identity with restrained supporting icon colors; avoid introducing green/teal as brand colors.

**Reason:** The reference provides a clearer, more approachable dashboard hierarchy while the active MVP remains focused on social content and publishing. Reusing existing API data avoids presenting mock numbers as real business activity.

## D-037 — Owner-controlled AI brand voice and safe administrator password recovery
**Date:** 2026-11-07  
**Decision:** Keep confirmed business facts, social-derived brand observations, and owner writing preferences separate. Add an explicit workspace `brand_voice_mode` (`automatic`, `manual`, `hybrid`) and `custom_ai_instructions`. Only the latest owner/admin-approved Brand Intelligence analysis may inform caption/video-script generation. Manual mode excludes social-derived voice guidance; automatic and hybrid modes include it; hybrid also includes the owner's explicit tone/phrase preferences. Custom owner instructions are passed separately as writing-style guidance and cannot override factual accuracy, safety, or platform rules.  
**Recovery decision:** Platform administrators may initiate a standard one-time password-reset flow only for an active non-admin customer with an already-verified email. The link is delivered to that verified address; the customer chooses the password. Older unused reset tokens are invalidated and the initiation is audited. Administrators never view or set passwords. Accounts without verified email require a separate stronger identity-verification process; no admin impersonation or email ownership bypass is introduced.  
**Reason:** Social media is useful evidence of communication style but must not silently replace business-owner decisions. Customers need control over niche and brand voice. Account support must be possible without creating an administrator backdoor.

## 2026-11-07 — Resend as the first API campaign provider (Increment 51)
**Decision:** Keep SMTP as the default and as the existing transactional email transport, while adding Resend as an explicitly selected provider for platform announcement campaigns. Use stable campaign/recipient idempotency keys, persist provider message IDs, and accept only timestamp-bounded Svix-verified webhook events. Persist provider event IDs for replay-safe processing and globally suppress hard bounces and spam complaints.
**Rationale:** Resend exposes a direct HTTP email API with idempotency keys and signed delivery webhooks. This closes key limitations of SMTP campaign delivery without migrating password recovery and billing email flows in the same increment. The integration uses the standard library rather than adding an SDK dependency.
**Trade-offs:** Provider choice is currently configuration-based and Resend-specific; the app is not yet provider-neutral. Resend idempotency keys are documented as retained for 24 hours. SMTP fallback remains available but cannot provide provider idempotency or delivery events.
