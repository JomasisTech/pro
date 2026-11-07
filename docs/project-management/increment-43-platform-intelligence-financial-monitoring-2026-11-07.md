# Increment 43 — Platform Intelligence & Financial Monitoring

Date: 2026-11-07  
Base: `autobizpro-profile-ai-recovery-increment31.zip`

## Purpose
Extend the existing `/platform` owner console and `/api/v1/platform-admin` API. Reuse existing payment, subscription, usage, activity, content, social-account and organization records. Do not create a second billing or customer system.

## Implemented in this increment

### Administrator entry point
- Added frontend route `/admin/login`.
- It links to the existing secure `/login?next=%2Fplatform` flow; it does not create a second credential store or bypass the server-side `require_platform_admin` check.
- Existing backend admin authorization remains authoritative.

### Login telemetry
- Added `PlatformLoginEvent` model and migration `20261107_0043_platform_login_events.py`.
- Successful email/password logins are recorded with user ID, method, timestamp and bounded user-agent string.
- Raw IP addresses and passwords are deliberately not stored in this telemetry table.
- Historical logins cannot be reconstructed; events begin after migration/deployment. This increment does not yet instrument OAuth/WhatsApp sign-ins or failed sign-in attempts.

### Customer inspection
`GET /api/v1/platform-admin/customers/{user_id}` now additionally returns:
- `social_accounts`: provider, account name/type, status, connection and last-sync timestamps. OAuth tokens/secrets are never returned.
- `business_profiles`: business name, industry ID, niche and description (no credential fields).
- `recent_content`: recent draft metadata and a 240-character content preview.
- `scheduled_posts`: recent scheduled-post metadata; content and provider secrets are not exposed.
- `usage`: aggregated usage-event quantity by metric for the customer's organizations.
- `login_history`: up to 20 recorded successful password sign-ins.

### Global platform activity
- Added `GET /api/v1/platform-admin/activity?limit=...` aggregating existing organization activity logs across organizations.
- The API includes organization and actor details and is protected by `require_platform_admin`.
- It only displays actions already emitted by application code. Missing instrumentation remains missing; do not assume every click or action is tracked.

### Financial and usage analytics
- Added `GET /api/v1/platform-admin/financials?days=90`
- `GET /api/v1/platform-admin/cost-entries?limit=100`
- `POST /api/v1/platform-admin/cost-entries` (administrator-verified expense entry).
- Returns confirmed paid revenue, pending amounts, monthly revenue grouped by currency, and usage totals grouped by metric.
- Currency totals remain separate; values are minor units and no FX conversion is guessed.
- Added administrator-managed operating cost ledger (`GET/POST /api/v1/platform-admin/cost-entries`) for verified hosting, AI provider, image/video, storage/bandwidth, email/messaging and other expenses. Entries include provider, description, currency and service period; creation is audit logged.
- Financial response now reports recorded costs by currency. It explicitly warns that unentered vendor invoices and refunds/chargebacks are not included. Do not label partial expense data as net profit or estimate monetary AI costs from event counts.

### Frontend `/platform`
- Added financial monitoring panel with currency-separated paid revenue and usage totals.
- Added successful sign-in timeline.
- Added organization activity feed.
- Customer inspection modal now includes connected social accounts, content previews and login history.

## API contracts
- `GET /api/v1/platform-admin/financials?days=90`
- `GET /api/v1/platform-admin/cost-entries?limit=100`
- `POST /api/v1/platform-admin/cost-entries` (administrator-verified expense entry)
- `GET /api/v1/platform-admin/activity?limit=30`
- `GET /api/v1/platform-admin/login-events?limit=30`
- Existing customer detail endpoint enriched as above.

All endpoints depend on `require_platform_admin`. Keep this server-side authorization on every new admin route.

## Migration
Run `alembic upgrade head` in the backend deployment. New revisions: `20261107_0043` (login telemetry), parent `20261107_0042`; and `20261107_0044` (manual operating-cost ledger), parent `20261107_0043`.

## Important limitations / next work
1. Login telemetry currently covers successful password login only. Add provider-aware events for Google, WhatsApp and future SSO, plus carefully designed failed-login telemetry with privacy/rate controls.
2. Add automated provider cost ingestion (AI model/token rates, image/video generation rates, storage/egress, hosting invoices) so the manual expense ledger can be reconciled with actual metered usage.
3. Add refund and chargeback entities/reconciliation before net revenue or profit is displayed.
4. Add per-customer activity filtering, pagination and date ranges; current global activity is latest-N only.
5. Add admin role hierarchy, mandatory MFA enforcement for platform admins, and a formal step-up/approval workflow for sensitive actions.
6. Add privacy/retention policy for customer content previews and login telemetry; consider configurable retention and access audit events.
7. Verify `next` redirect handling in login; the admin login page currently routes to the existing login page with `next=/platform`. The platform page and backend still enforce admin access.
8. Verify PostgreSQL behavior and run full frontend build/tests in CI. SQLite-only tests do not prove PostgreSQL production readiness.

## Developer handover
Read this document after `docs/project-management/HANDOVER.md`. Existing payment, subscription, usage and organization activity models are the source of truth. Keep financial reporting transparent about data gaps. Never expose social OAuth credentials, passwords, reset tokens, raw private messages or sensitive user data in admin APIs.
