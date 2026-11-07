# Increment 51 — Resend campaign provider and delivery events (2026-11-07)

## Scope

Add a real provider API for platform announcement campaigns while preserving SMTP for existing transactional email flows. The selected first campaign provider is Resend. This is a provider-specific first adapter, not a general provider registry.

## Implemented

- Added `EMAIL_CAMPAIGN_PROVIDER` (`smtp` or `resend`), `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`, and bounded `EMAIL_PROVIDER_TIMEOUT_SECONDS` settings.
- Added a standard-library HTTP adapter at `backend/app/integrations/resend_email.py`. It sends plain-text messages through `POST https://api.resend.com/emails`, returns the provider message ID, and classifies permanent HTTP errors separately from transient failures.
- Campaign requests use a stable idempotency key derived from campaign and recipient IDs. Resend documents idempotency for email requests and retains keys for 24 hours; retrying with the same key and payload avoids a duplicate send within that window.
- The durable campaign worker selects Resend or the existing SMTP adapter based on configuration and stores the Resend message ID for webhook correlation. Existing password-reset, verification and billing email callers continue to use SMTP.
- Added `POST /api/v1/platform-admin/public/email/resend-webhook`. It verifies Svix signatures against the exact raw request body, enforces a five-minute timestamp tolerance, and deduplicates events by the provider event ID.
- `email.delivered` updates the recipient to delivered. `email.bounced` and `email.complained` update the recipient state and add a global suppression (`bounce` or `complaint`) so future announcement campaigns exclude that address.
- Added provider event ledger table and migration `20261107_0050`.
- Platform dashboard campaign history now has an Analytics action showing delivered, pending, retry, bounced, complaint and unsubscribe counts. It also explains provider/webhook behavior.
- Added provider configuration examples to `backend/.env.example`.

## Configuration

For campaign delivery through Resend:

```env
EMAIL_CAMPAIGN_PROVIDER=resend
RESEND_API_KEY=re_...
RESEND_WEBHOOK_SECRET=whsec_...
EMAIL_PROVIDER_TIMEOUT_SECONDS=15
EMAIL_FROM=AutoBizPro <verified-sender@your-domain.example>
```

Keep SMTP configured for transactional account and billing emails; this increment does not migrate those flows to Resend.

Register the Resend webhook at:

`https://YOUR_API_HOST/api/v1/platform-admin/public/email/resend-webhook`

Subscribe to `email.delivered`, `email.bounced`, and `email.complained`. Copy its signing secret to `RESEND_WEBHOOK_SECRET`. Never put either secret in frontend variables or commit them.

## Verification

- `python -m compileall -q backend/app backend/migrations backend/scripts`: passed.
- Fresh SQLite Alembic upgrade through `20261107_0050`: passed.
- `alembic check`: passed with no schema drift.
- Mocked Resend adapter success check: passed; verified returned provider ID, recipient payload, configured timeout and stable idempotency header.
- Pytest collection for the new adapter tests was attempted but blocked because this environment lacks `pyotp`, imported by the shared test `conftest.py`. No full test suite result is claimed.
- Frontend dependencies remain unavailable; lint, TypeScript check, production build and browser QA remain unverified.
- No live Resend credentials, verified sender domain, public webhook URL or real provider events were available. Live sending and webhook verification remain unverified.

## Remaining risks / next work

- SMTP campaign mode remains at-least-once and cannot guarantee duplicate prevention. Use Resend for campaigns where provider idempotency is required.
- Resend's idempotency window is 24 hours. Longer recovery windows need provider-side reconciliation before retrying an old ambiguous attempt.
- A provider event arriving before the send response has been committed can race message-ID persistence; a later reconciliation/replay mechanism should close this rare edge case.
- Worker still assumes a single scheduler instance. Add a database lease/claim protocol before running multiple campaign workers.
- Add full API tests for valid/invalid signatures, replayed events, delivered/bounce/complaint suppression and duplicate concurrent webhook delivery.
- Verify live provider setup and delivery, including domain authentication (SPF/DKIM/DMARC), webhook replay and sender reputation before production use.
- Campaign analytics currently treat provider-reported delivered as sent for the combined sent total; the separate delivered count is the authoritative inbox-provider acceptance signal. Open/click tracking is intentionally not included.
