# Increment 50 — Durable email campaign processing and unsubscribe controls

## Scope

Hardened the owner-only platform announcement feature introduced in Increment 49. This is still for service/platform announcements, not a general-purpose marketing automation product.

## Changes

- Added migration `20261107_0049_email_queue_retries_unsubscribe.py`.
- Campaigns and recipient snapshots remain in the database as the durable queue. Removed reliance on FastAPI `BackgroundTasks` for actual delivery.
- Added `backend/scripts/process_email_campaigns.py`, a repeatable scheduler/cron entry point. Run from `backend/` using `python -m scripts.process_email_campaigns`.
- Worker persists recipient attempts individually and retries temporary SMTP failures with bounded exponential delays, up to three attempts. Failed recipients can be re-queued by the owner through `POST /api/v1/platform-admin/email-campaigns/{campaign_id}/retry-failed`.
- Added per-recipient opaque unsubscribe capabilities and global normalized email suppression. New campaigns exclude suppressed addresses. A public `POST /api/v1/platform-admin/public/email/unsubscribe?token=...` endpoint applies suppression; the frontend confirmation/status page is `/email/unsubscribe`.
- Added owner-only campaign analytics endpoint `GET /api/v1/platform-admin/email-campaigns/{campaign_id}/analytics` with sent, pending, retry, failed, bounced and unsubscribed counts. The dashboard now exposes retry for failed recipients and describes the scheduler requirement.
- Added migration fields for attempts, retry schedule, provider message ID placeholder and delivery/bounce timestamps. Provider webhook bounce ingestion is not connected yet; therefore bounce counts remain zero unless a provider integration is added.

## Operational setup

1. Deploy code and run `alembic upgrade head`.
2. Configure valid SMTP settings and a verified sender.
3. Run a single scheduled worker instance from the backend directory, e.g. every minute: `python -m scripts.process_email_campaigns`.
4. Monitor worker stdout/logs and the owner dashboard campaign history. Do not run multiple workers concurrently: this lightweight worker intentionally assumes a single scheduler instance; distributed locking/lease ownership is a future improvement.

## Delivery semantics and limitations

- SMTP acceptance is recorded as `sent`; it does not prove inbox delivery.
- Retries are at-least-once. If the SMTP server accepts a message but the connection drops before acknowledgement, a retry may cause a duplicate. Provider idempotency and message-event webhooks are future work.
- Bounce/complaint webhooks, provider message IDs, suppression from hard bounces/complaints, campaign open/click tracking, and a complete retention policy are not implemented.
- Unsubscribe applies globally to future platform announcement campaigns. Essential account/security/billing messages are unaffected.
- Worker currently processes campaigns in batches of up to 100 recipients per invocation. A cron/scheduler must invoke it frequently enough to complete large campaigns.

## Verification

- `python -m compileall -q backend/app backend/migrations backend/scripts`: passed.
- Fresh SQLite `DATABASE_URL=sqlite:////tmp/autobizpro_increment50.db python -m alembic upgrade head`: passed through `20261107_0049`.
- ZIP integrity: verify after packaging.
- Full backend tests, frontend lint/typecheck/build, PostgreSQL migration/integration tests and live SMTP delivery were not run in this environment.
