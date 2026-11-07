# Billing and payment integration

**Last updated:** 2026-11-04 — Increment 19

## Current architecture

BizPilotPro uses one billing domain with provider adapters behind `backend/app/integrations/payments/base.py` and `registry.py`.

- **Paystack:** first implemented provider. Hosted checkout and transaction verification are used.
- **Google Pay:** a Paystack Checkout payment channel, not a separate processor. Availability depends on Paystack merchant configuration and customer/device/card eligibility. Keep Card enabled in Paystack.
- **PayPal:** future provider; registered in the provider catalog but no adapter or checkout is implemented.
- **Flutterwave:** future provider; registered in the provider catalog but no adapter or checkout is implemented.

Adding a provider later should mean implementing the shared checkout/verification/webhook contract and registering its adapter. The shared price catalog, subscriptions, customer billing page, payment records and audit trail should not need provider-specific rewrites.

## Approved initial price catalogue

Prices are stored in integer minor units (NGN kobo, USD cents). The database catalog is authoritative; the browser never supplies the amount.

| Plan | Currency | Monthly | Annual |
|---|---|---:|---:|
| Free | NGN/USD | 0 | 0 |
| Standard | NGN | ₦7,500 | ₦75,000 |
| Premium | NGN | ₦15,000 | ₦150,000 |
| Standard | USD | $9.99 | $99.90 |
| Premium | USD | $19.99 | $199.90 |

Annual prices are ten monthly payments (two months' equivalent discount). The 7-day Premium trial is not configured. Taxes, refund policy and cancellation policy still need final product/legal decisions.

## Customer billing workflow implemented in Increment 12

### Checkout

`POST /api/v1/billing/organizations/{organization_id}/checkout`

- Requires an authenticated workspace owner or admin.
- Request accepts `plan_id`, `currency`, `billing_interval`, provider `paystack`, and optional `recurring_consent` (default false).
- The customer-facing checkbox is optional. If unchecked, checkout is one-time only. If checked, the server stores a timestamp, consent-version identifier and server-authored wording snapshot against the payment attempt. The UI explicitly states automatic renewal is not active yet and that the customer will be notified before it is activated. Consent is not inferred from a successful card payment.
- Backend reads the enabled price from `billing_prices`, creates a pending `payment_transactions` snapshot, writes `billing.checkout_started` activity, then initializes Paystack Checkout.
- Amount, currency, email, organization, plan and reference are derived or validated server-side; no client-provided amount is accepted.
- Checkout callback points to `${FRONTEND_BASE_URL}/billing/return`.

### Browser return verification

`POST /api/v1/billing/organizations/{organization_id}/transactions/{reference}/verify`

- Requires workspace owner/admin.
- The browser-returned reference is only a lookup key. Backend fetches the transaction directly from Paystack and compares status, reference, exact amount, currency and customer email against the saved snapshot.
- Only a verified successful charge can mark the transaction paid and activate the subscription.
- If the payment attempt contains explicit recurring consent, and Paystack's verified transaction contains an authorization object with `reusable: true`, the service may retain the authorization code encrypted. It preserves the exact checkout email as the future charge email. It stores only limited card display metadata (last four, type and expiry); PAN/CVV are never stored.
- Authorization storage requires the dedicated backend-only `BILLING_AUTHORIZATION_ENCRYPTION_KEY` Fernet key. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and keep it in the deployment secret manager. Do not reuse `SOCIAL_TOKEN_ENCRYPTION_KEY`. Back up and protect this key; losing it makes stored authorizations undecryptable. Rotating it requires a controlled decrypt/re-encrypt migration or key-versioning procedure.
- If consent is absent, the authorization is not retained. If Paystack marks the authorization non-reusable, it is not retained. If the dedicated encryption key is absent, reusable authorization storage is skipped; the verified initial payment can still be fulfilled.

### Paystack webhook

`POST /api/v1/billing/webhooks/paystack`

- Reads exact raw request bytes and verifies the Paystack signature before JSON processing.
- Persists a minimal receipt with SHA-256 payload digest (not raw body) and a unique event key.
- Handles `charge.success` by performing the same server-to-server transaction verification and fulfillment as the browser return.
- Duplicate processed events do not activate or extend a subscription twice. Failed processing can be retried by Paystack; a `processing` receipt left by a crashed worker currently needs manual reconciliation.
- Non-success event types are recorded and ignored. Refunds, disputes, reversals and subscription cancellation are not yet implemented.

### Subscription state

- Successful verification updates `subscriptions` and `organizations.plan` in one database transaction and records `billing.subscription_activated` activity.
- Existing paid subscriptions are not changed by admin price edits.
- A separately paid same-plan checkout extends from the later of now or the current period end. A different-plan checkout takes effect immediately.
- Increment 19 adds a durable renewal-attempt ledger and an opt-in CLI worker. It charges only subscriptions with explicit stored consent, a Paystack `reusable: true` authorization, encrypted authorization code, retained original email, active/past-due state, and an elapsed billing period. Each subscription/period has a unique attempt; ambiguous provider timeouts are reconciled by verification only and never charged again automatically for that same period. A Paystack `pending`/`ongoing`/`otp` response is recorded as `needs_action` and is not retried. The customer-facing challenge-completion UX, renewal reminders, automated bounded retries, and full production operations are still incomplete. The worker is disabled by default; do not enable it until the remaining checklist below is completed. Cancellation-at-period-end is honored by excluding cancelled-at-period-end subscriptions.

## Admin and customer frontend

- Customer billing page: `/billing` (owner/admin can start checkout; all workspace members can view the subscription).
- Payment return/status page: `/billing/return`.
- Platform-owner price editor: `/platform/billing-prices`.
- Price APIs: `GET /api/v1/billing/admin/prices`, `PUT /api/v1/billing/admin/prices`.
- Platform price administration requires a verified account email listed in `PLATFORM_ADMIN_EMAILS`.
- Workspace member management remains under `/workspace`; account security is under `/security`.
- There is not yet a platform-wide customer-account console for listing/suspending/deleting all customer users or switching into customer workspaces.

## Configuration

Backend environment variables:

```env
PAYSTACK_PUBLIC_KEY=
PAYSTACK_SECRET_KEY=
PAYSTACK_WEBHOOK_SECRET=
BILLING_AUTHORIZATION_ENCRYPTION_KEY=
BILLING_RENEWALS_ENABLED=false
PLATFORM_ADMIN_EMAILS=owner@example.com
FRONTEND_BASE_URL=https://your-frontend-domain.example
```

Keep Paystack secret/webhook keys backend-only. Configure the Paystack dashboard webhook URL as:

`https://your-api-domain.example/api/v1/billing/webhooks/paystack`

Configure the webhook signing secret and test with Paystack test keys first. Google Pay must be enabled in the merchant dashboard; it appears within Paystack Checkout only when eligible. Do not create a separate Google Pay adapter.

Automatic renewal worker (Increment 19; disabled by default):

```bash
cd backend
python -m app.jobs.process_subscription_renewals
```

The command exits without charging while `BILLING_RENEWALS_ENABLED=false`. Keep it false until Paystack test-mode recurring charges, 3DS/customer-action handling, customer notices and support procedures have been verified. If enabled, run from one dedicated scheduler initially; do not attach it to every API replica. The worker performs at most one charge initiation per subscription period. Network-ambiguous attempts are verification-only on subsequent runs; no automatic retry is attempted.

Apply migrations with:

```bash
cd backend
alembic upgrade head
```

Increment 12 adds migration `20261104_0031`, storing the selected billing interval on each payment attempt. Increment 18 adds `20261104_0034` for consent and encrypted authorization storage. Increment 19 adds `20261104_0035` for the unique subscription-period renewal ledger.

## Verification performed in Increment 12

- `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_billing_checkout_fulfillment.py tests/test_paystack_checkout.py tests/test_billing_price_admin.py tests/test_billing_readiness.py tests/test_paystack_transactions.py tests/test_paystack_signatures.py` — **31 passed**.
- `python -m compileall -q backend/app backend/tests` — passed.
- Alembic upgrade to head, downgrade to `20261104_0030`, and re-upgrade to head all passed using a persistent file-backed SQLite database.
- Frontend dependencies are absent in the current environment; ESLint, TypeScript, Next.js build and browser/mobile tests were not run.
- No live Paystack request, webhook, real Google Pay transaction, PostgreSQL 16 test, or production payment was performed.

## Remaining work

1. Verify migration `20261104_0031` upgrade/downgrade/re-upgrade using a persistent SQLite database and PostgreSQL 16.
2. Install frontend dependencies and run lint, typecheck, production build and browser/mobile QA.
3. Configure Paystack test keys and webhook URL; run real test-mode checkout, webhook retries, invalid signatures, failed payments and Google Pay eligibility checks.
4. Add webhook stuck-processing recovery/reconciliation and robust concurrency tests against PostgreSQL.
5. Implement renewals, cancellation, refunds, disputes/chargebacks, failed-payment grace periods, receipts/invoices and customer self-service.
7. Add PayPal and Flutterwave adapters only after account eligibility, merchant approval and payment flows are confirmed.
8. Add AI model/provider cost tracking and admin cost settings. Provider cost alerts may be automated where reliable official data exists; customer subscription price increases must remain manually approved.
9. Decide tax, refund, cancellation and trial policy before public launch.

## Increment 13 — Platform billing operations and live-test checklist

The platform-owner dashboard at `/platform` now exposes safe Paystack key configuration status (test/live/unknown inferred from key prefixes), webhook-secret presence, recent payment transactions, recent webhook outcomes, and aggregate pending/failed counts. It never returns credential values. This is a configuration diagnostic, not a live API connectivity test.

Before production activation, perform the following with the merchant's Paystack test credentials and deployed HTTPS URLs:

1. Configure `PAYSTACK_PUBLIC_KEY`, `PAYSTACK_SECRET_KEY`, and `PAYSTACK_WEBHOOK_SECRET` on the backend only. Confirm the dashboard reports **test** mode and both credential checks are configured.
2. Configure the Paystack webhook endpoint as `https://<api-domain>/api/v1/billing/webhooks/paystack` and the frontend return URL as `https://<frontend-domain>/billing/return`.
3. Start a test NGN Standard checkout. Confirm Paystack opens, completes with a test card, and redirects to the return page.
4. Confirm the return page calls the authenticated verification endpoint and the backend independently verifies reference, amount, currency, status, and customer email before activating the subscription.
5. Confirm the corresponding webhook is accepted, stored once, and shown as processed. Redeliver the same event and confirm it is harmlessly deduplicated.
6. Repeat with USD only after Paystack has enabled USD for the merchant account. Test Google Pay only on a supported device/browser with an eligible Google Pay wallet/card; its appearance is controlled by Paystack and eligibility, not guaranteed by the application.
7. Test invalid signatures, amount/currency mismatches, failed/cancelled checkout, duplicate callbacks, and provider timeouts. No failed or mismatched payment may activate a plan.
8. Only after successful test-mode evidence, switch backend keys and webhook configuration to live credentials. Never use test credentials in production or expose secret keys to the browser.

Increment 13 adds a platform-admin customer directory, account suspension/reactivation, audit trail, and payment diagnostics. Suspension invalidates existing user sessions. Admin payment diagnostics are read-only; manual retry, refunds, cancellation, recurring renewals, and reconciliation are not implemented.

## Increment 14 — administrator webhook recovery

- Added `POST /api/v1/platform-admin/webhooks/{event_id}/retry`, protected by the verified platform-owner allowlist.
- Only failed webhook receipts, or `processing` receipts whose original receipt timestamp is older than ten minutes, can be retried. Recent `processing` events are rejected to reduce concurrent duplicate work.
- Only Paystack `charge.success` events with a transaction reference are eligible. The retry does not trust stored webhook payloads or grant access from the event itself: it retrieves the transaction from Paystack and reuses the normal expected-reference/amount/currency/customer verification and idempotent subscription fulfillment service.
- Retry attempts and outcomes are written to `platform_admin_audits`. A failed provider request remains retryable; a mismatch is rejected and remains failed for investigation.
- `/platform-admin/billing-operations` now returns webhook receipt IDs so the dashboard can offer a retry action for failed charge-success events.
- This is a manual recovery tool, not an automatic background reconciler. Live Paystack, PostgreSQL row-lock/concurrency behavior, and real webhook delivery remain unverified.


## Increment 15 — scheduled payment reconciliation

- Added `backend/app/modules/billing/reconciliation.py`, a bounded, repeatable reconciliation pass for Paystack payment attempts that remain `pending` for at least 10 minutes. It uses the provider-neutral payment registry, retrieves each transaction directly from Paystack, and reuses `verify_and_activate`; it never trusts stored webhook payloads or browser return parameters.
- A successful provider verification fulfills the subscription through the existing row-locked/idempotent service. Explicit failed/abandoned provider statuses are marked failed by that service. Provider timeouts and mismatches are counted separately and do not grant access. Providers not yet implemented (PayPal/Flutterwave) are skipped.
- Added platform-owner endpoint `POST /api/v1/platform-admin/billing/reconciliation/run` with bounded `limit` (1–100) and age threshold (5–1440 minutes), plus an audit record. Added a **Run reconciliation** action to `/platform`.
- Added scheduler entry point `python -m app.jobs.reconcile_payments` (run from `backend/`). Configure the hosting provider's scheduled-job/cron facility to execute it every 5–10 minutes. It processes up to 50 old pending payments per run and prints a JSON summary. No in-process timer or background thread is started by FastAPI.
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_payment_reconciliation.py tests/test_platform_admin.py tests/test_billing_checkout_fulfillment.py` from `backend/` — **13 passed**; `python -m compileall -q app tests` passed. Tests use SQLite and mocked Paystack responses.
- Not verified: PostgreSQL row-lock/concurrency behavior, live Paystack test mode, deployment scheduler configuration, frontend build/browser behavior, and real merchant transactions.

Example Linux cron entry (adjust the absolute backend path and virtual-environment path to the deployment):

```cron
*/10 * * * * cd /srv/bizpilotpro/backend && /srv/bizpilotpro/backend/.venv/bin/python -m app.jobs.reconcile_payments >> /var/log/bizpilotpro-payment-reconciliation.log 2>&1
```

On managed hosting, use its scheduled-job feature with the same working directory and command rather than assuming shell cron is available.


## Increment 16 — subscription lifecycle management

- Customer owners can schedule cancellation at the end of the already-paid period with `POST /api/v1/billing/organizations/{organization_id}/subscription/cancel`. The paid plan remains active until the period boundary; cancellation does not issue a refund.
- Owners can reverse a scheduled cancellation before the period ends with `POST /api/v1/billing/organizations/{organization_id}/subscription/resume`. These actions are tenant-scoped, owner-only and written to the organization activity log.
- Customer billing now shows recent payment attempts (maximum 50) through `GET /api/v1/billing/organizations/{organization_id}/transactions`, including failed/pending/paid statuses. It does not expose raw provider payloads or secret data.
- A scheduled lifecycle processor handles due subscriptions. At the paid period boundary, a customer-requested cancellation changes status to `cancelled` and downgrades the organization to Free. Otherwise the subscription enters `past_due` for a configurable renewal grace period; the organization retains its paid plan during grace. At grace expiry, status becomes `expired` and the organization is downgraded to Free.
- Grace duration is configured by backend-only `BILLING_GRACE_PERIOD_DAYS` (default 3, allowed 0–14; set 0 to disable grace). This default is an operational starting policy and should be reviewed before public launch.
- Scheduled job entry point: `python -m app.jobs.process_subscription_lifecycle`, run from `backend/`. Configure a hosting scheduled job every 15–60 minutes. It performs no charge and does not create an automatic renewal; customers must still initiate a new checkout.
- Increment 16 migration: `20261104_0033` adds `subscriptions.grace_period_ends_at` and `subscriptions.cancellation_requested_at`.
- Verification: focused lifecycle, billing fulfillment, payment reconciliation and platform admin tests — **18 passed** using SQLite and mocked Paystack where relevant; Python compile passed; migration upgrade/downgrade/re-upgrade and Alembic schema comparison passed on SQLite.
- Not verified: PostgreSQL 16 behavior, real Paystack/Google Pay, hosting scheduler execution, frontend build/browser/mobile workflow, or production subscription behavior.

### Current lifecycle limitations

- Renewal remains customer-initiated. The lifecycle processor only manages access expiry and grace periods; it does not create recurring charges.
- No email/SMS renewal reminders, card update flow, provider-side recurring authorization, refund/dispute handling, downloadable tax invoices or receipts are included in this increment.
- A failed checkout attempt is visible in payment history but does not mark an otherwise-current subscription past due. Past-due status is entered when the paid period ends without a verified renewal.

### Lifecycle scheduler example

Run this separately from pending-payment reconciliation. Example cron (replace paths with the deployment's actual backend and virtual environment paths):

```cron
*/30 * * * * cd /srv/bizpilotpro/backend && /srv/bizpilotpro/backend/.venv/bin/python -m app.jobs.process_subscription_lifecycle >> /var/log/bizpilotpro-subscription-lifecycle.log 2>&1
```

A managed-host scheduler should use the same working directory, command and backend environment variables. Do not run the lifecycle processor from multiple unsupervised application processes; its row locking and bounded processing are designed for scheduled invocation, and PostgreSQL concurrency must still be validated.


## Increment 17 — Paystack recurring-charge adapter foundation

- Added `PaystackProvider.charge_authorization`, a server-side adapter method for Paystack's `POST /transaction/charge_authorization` endpoint. It sends the stored authorization code, the original authorization email, a server-selected amount/currency, a unique reference, and metadata.
- The adapter validates the authorization-code shape, positive amount, supported NGN/USD currencies, and Paystack-safe unique reference characters before making the request. It validates the returned reference and returns the provider transaction data for a separate verification/fulfillment workflow.
- The adapter deliberately does **not** store authorization codes, schedule charges, mark subscriptions paid, or activate/extend plans. Those actions require explicit recurring-payment consent, secure encrypted authorization storage, durable renewal-attempt records, webhook/verify handling, retry policy, customer notices, and cancellation safeguards.
- Paystack documentation states that only authorizations marked `reusable: true` should be charged; the original email used to create the authorization must be retained. A successful first transaction's authorization object can be retrieved from transaction verification/webhooks. See [Paystack recurring charges](https://paystack.com/docs/payments/recurring-charges/) and [Charge Authorization API](https://paystack.com/docs/api/transaction/).
- Verification: `DATABASE_URL=sqlite+pysqlite:///:memory: python -m pytest -q tests/test_paystack_checkout.py tests/test_billing_checkout_fulfillment.py tests/test_subscription_lifecycle.py tests/test_payment_reconciliation.py` — **17 passed**.
- Not verified: live Paystack test-mode recurring debit, PostgreSQL behavior, card issuer/3DS challenges, frontend consent UX, authorization encryption/storage, scheduled renewals, retries, receipts, and email notifications. No migration was required.

### Recurring billing safety requirements before activation

1. Obtain explicit customer consent to automatic renewal and disclose plan, amount, currency, interval, and cancellation terms before initial checkout.
2. Persist only authorizations that Paystack marks `reusable: true`; encrypt authorization codes at rest and retain the exact authorization email. Never store PAN/CVV.
3. Create one durable renewal attempt and unique reference per billing period; lock the subscription and enforce idempotency.
4. Treat charge initiation as pending, not paid. Verify the returned reference with Paystack and fulfill only after a verified successful transaction/webhook.
5. Handle `paused`/3DS challenge responses by asking the customer to complete authentication; do not retry blindly.
6. Do not charge subscriptions with `cancel_at_period_end`, expired, suspended, or otherwise ineligible states.
7. Add bounded retries and customer notifications; do not repeatedly charge a declined/invalid authorization.
8. Make the feature opt-in and disabled until test-mode verification and legal/merchant policy review are complete.


## Increment 18 — recurring consent and authorization storage

- Customer `/billing` presents an optional consent checkbox to prepare a reusable authorization for possible future renewals. The UI states that automatic renewal is not active yet and that the customer will be notified before it is activated. Leaving it unchecked remains a one-time checkout.
- Checkout records a server timestamp, consent version and wording snapshot in `payment_transactions`; it does not trust browser-provided amounts or authorization data.
- Verified reusable Paystack authorization is retained only when the matching payment has consent and a dedicated Fernet key is configured. Authorization code is stored as ciphertext in `subscriptions`; exact original checkout email and limited card display metadata are retained. No PAN/CVV are stored.
- Migration `20261104_0034` adds consent and authorization-storage columns. Apply with `alembic upgrade head`.
- **Automatic renewals remain disabled.** No renewal scheduler, durable renewal attempts, 3DS handling, retry policy, customer notices or recurring payment fulfillment has been implemented. Do not schedule or call the charge adapter as an unattended job yet.


## Increment 21 — customer authorization revocation

The customer billing page now displays whether a reusable Paystack authorization is stored and safe card metadata (card type and last four digits). Only the workspace owner can deactivate the saved authorization. The backend calls Paystack `POST /customer/authorization/deactivate` with the decrypted authorization code; the code and ciphertext never leave the server. Local ciphertext and card metadata are cleared only after Paystack confirms deactivation. If the provider request fails or its outcome is ambiguous, the authorization remains encrypted locally and the UI reports an error rather than claiming success. Historical consent evidence remains available for audit.

This is a revocation control, not an automatic-renewal activation. `BILLING_RENEWALS_ENABLED` remains false. OTP/3DS customer-action completion, renewal notifications, safe bounded retries, live Paystack test-mode validation, PostgreSQL concurrency checks and frontend browser/build QA are still required.


## Customer authentication for recurring charges — Increment 22

Paystack may return a paused recurring charge with `data.paused=true` and an `authorization_url` when an issuer requires OTP, PIN/OTP or 3DS. The renewal worker records the attempt as `needs_action`, stores the URL only for the exact HTTPS host `checkout.paystack.com`, and sends a callback URL to the customer billing page. The customer completes authentication with Paystack and returns to `/billing?renewal_reference=...`. The frontend then calls the tenant-scoped renewal verification endpoint. BizPilotPro verifies the transaction directly with Paystack and only then extends the subscription.

A customer-action attempt is not charged again by the scheduler. The challenge URL is shown only to workspace owners/admins; workspace members see that an owner/admin action is needed. If verification is still pending, the attempt remains available for another verification. If Paystack confirms a decline, the attempt is marked failed. Do not infer payment success from the redirect or query string.

Official references: [Paystack Recurring Charges — Two-factor authentication](https://paystack.com/docs/payments/recurring-charges/) and [Paystack Verify Payments](https://paystack.com/docs/payments/verify-payments/).

**Automatic renewals remain disabled.** Renewal notifications, bounded retry rules, live issuer challenge testing, PostgreSQL concurrency verification and production scheduler operations are still required.


## Increment 23 — customer notices before automatic renewal

Billing email notices use a durable `billing_notifications` outbox. The scheduled command is:

```bash
cd backend
python -m app.jobs.process_billing_notifications
```

Run it daily or every few hours, and schedule it before the automatic-renewal worker. Configure SMTP using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_STARTTLS`, and `EMAIL_FROM`. Set `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=true` only after SMTP is verified. `BILLING_RENEWAL_REMINDER_DAYS` defaults to 3 and accepts 1–14.

The job queues a one-time activation notice for each active subscription with explicit recurring consent and a verified reusable authorization. It also queues advance reminders for later renewal periods, and the renewal processor queues action-required and confirmed-decline messages. A notice is considered delivered only after SMTP returns success. The successful activation notice timestamp is persisted on the subscription; without it, the renewal worker will not charge that subscription. New reusable authorizations reset the timestamp, and authorization revocation clears it.

SMTP delivery uses bounded retries (five attempts) and a 20-minute stale-worker lease. SMTP and the database cannot share one atomic transaction, so a process crash after SMTP accepts a message but before the outbox commit can cause a duplicate on recovery. Inspect terminal `failed` outbox rows and SMTP logs operationally.

`BILLING_RENEWALS_ENABLED` remains `false` by default. Settings validation rejects enabling it unless `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=true`, `SMTP_HOST` is present, and the Paystack secret/encryption key are configured. This is only a configuration safeguard: it does not prove SMTP deliverability or live Paystack readiness. PostgreSQL, live Paystack/issuer challenges, and scheduler supervision still require verification.


## Increment 24 — recovery of interrupted renewal attempts

Run the verification-only recovery command from `backend/`:

```bash
python -m app.jobs.reconcile_subscription_renewals
```

Schedule it every 5–10 minutes. It checks a bounded batch of attempts whose status is `verification_pending`, plus `processing` attempts older than ten minutes. It verifies the existing payment reference directly with Paystack and uses the same server-side reference/amount/currency/email checks and subscription fulfillment path as normal payment verification. A confirmed decline is marked failed and queues the existing customer notice. A provider outage or mismatch remains pending/attention-required.

**This command never initiates a charge.** It is safe to run while `BILLING_RENEWALS_ENABLED=false`. Do not delete a stale renewal ledger row or create another charge for that subscription period to resolve an uncertain result. Automatic retries of declined/ambiguous/customer-action attempts remain intentionally disabled until Paystack-specific retryable response codes and limits are documented and live-tested.


## Increment 25 — provider-directed retry and operations supervision

The renewal ledger now stores `retry_at` and `retry_count` (migration `20261104_0039`). Paystack's adapter raises a distinct retry-window signal only for its explicit recurring-card regulator wait. The scheduler may then perform one delayed retry after the provider-stated time, while retaining the existing local payment reference and re-checking customer consent, authorization and period eligibility. A second regulator rejection is terminal for that period.

No automatic retry is allowed for generic declines, insufficient funds, customer authentication challenges, network timeouts or unknown/ambiguous results. Timeouts remain verification-only. This is an implementation of a documented provider response, not a claim of Paystack merchant-specific approval. Validate the response shape and same-reference behavior in Paystack test mode before enabling renewals.

Use the unified scheduler from `backend/`:

```bash
python -m app.jobs.run_billing_maintenance
```

The Render blueprint schedules it every five minutes. It queues/delivers notices first, reconciles uncertain references, processes eligible provider-directed retries, runs new due charges only if `BILLING_RENEWALS_ENABLED=true`, then applies lifecycle transitions. It emits structured JSON. Configure Render failure/missing-run notifications and operate only one managed scheduler. See [`operations/billing-scheduler.md`](operations/billing-scheduler.md).

Check database and optionally send a one-off SMTP test email to a controlled inbox:

```bash
python -m app.jobs.check_billing_readiness --email-to your-controlled-test-inbox@example.com
```

This sends a message only when `--email-to` is provided. Confirm inbox/spam delivery manually.

**Keep `BILLING_RENEWALS_ENABLED=false` and `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` until real SMTP, PostgreSQL 16, Paystack test-mode and scheduler deployment checks pass.**
