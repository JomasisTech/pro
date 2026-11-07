# Increment 44 — Provider-aware login telemetry

Date: 2026-11-07  
Base: Increment 43 platform intelligence and financial monitoring.

## Implemented

- Successful sign-ins now record their authentication method in `platform_login_events` for all currently implemented login paths: `password`, `google`, and `whatsapp`.
- Added one shared best-effort telemetry helper in `backend/app/api/v1/auth.py` so the three flows apply the same user-agent truncation and error handling.
- Telemetry persistence is isolated from authentication success: a database telemetry failure is rolled back and logged, but does not turn a valid sign-in into a failed sign-in.
- The existing platform login-history API and customer detail endpoint already return the `method` field, so provider-aware events appear in the existing admin views without a new endpoint or migration.

## Privacy and security decisions

- No raw IP address, password, OAuth token, WhatsApp one-time code, phone number, email address or provider subject is copied into the telemetry event.
- User-agent is bounded to 300 characters. Authentication method is bounded to 32 characters.
- Only successful authentication events are recorded. Failed attempts are intentionally not added in this increment because safely associating them with an account without storing raw identifiers requires a separate privacy, retention, aggregation and abuse-monitoring design.
- Existing server-side admin authorization continues to protect access to login history.

## Verification

- `python -m compileall -q backend/app backend/migrations` passed.
- Source inspection confirms password, Google callback and WhatsApp verification paths call the shared helper only after successful authentication and membership validation.
- Full auth/admin tests and frontend checks were not run in this environment because backend optional dependencies and frontend dependencies are not installed. This is not a claim of end-to-end provider login verification.
- No migration is required; the existing `platform_login_events.method` column already supports these values.

## Remaining work

1. Add privacy-reviewed, aggregated failed-login/security telemetry with retention limits and no raw account/IP identifiers.
2. Add admin login-history filtering by provider, customer and date range.
3. Add platform-admin MFA/step-up authentication and access-audit coverage.
4. Run Google and WhatsApp sign-in integration tests against configured test providers, plus PostgreSQL and frontend CI checks.
