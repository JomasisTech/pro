# Increment 52 — campaign worker coordination and webhook race recovery (2026-11-07)

## Implemented

- Added a singleton database-backed campaign-worker lease (`platform_email_worker_leases`) with a conditional atomic claim. Concurrent scheduler invocations cannot both claim the campaign queue while a valid lease is held.
- The worker renews its 15-minute lease between recipients and releases it on normal exit. If a process crashes, a later scheduler invocation can claim the queue after expiry.
- Added recovery for a provider webhook that arrives before the send response's provider message ID has been committed. The worker replays already-persisted delivery, bounce, or complaint events after saving the message ID; bounce/complaint replay also ensures global suppression.
- Added migration `20261107_0051`, parent `20261107_0050`.
- Existing SMTP/Resend selection, Resend idempotency keys, retries, unsubscribe checks and campaign analytics remain intact.

## Operations

Continue scheduling `python -m scripts.process_email_campaigns` from the backend directory. Multiple scheduler instances are now coordinated by the database lease, but use a shared production database and synchronized clocks. The lease is 15 minutes and is renewed between recipient sends. A process crash may delay resumption until the lease expires.

## Verification

- `python -m compileall -q backend/app backend/migrations backend/scripts`: passed.
- Fresh SQLite migration through `20261107_0051`: passed.
- Downgrade to `20261107_0050`, re-upgrade to head, and `alembic check`: passed; no schema drift detected.
- Worker CLI empty-queue smoke test: passed (`processed=0`).
- SQLite lease contention/release smoke test: first owner acquired, competing owner was rejected, and a subsequent owner acquired after release. This validates the conditional-update logic in SQLite, not a multi-process PostgreSQL race.
- Live PostgreSQL concurrency, multiple-process race test, live Resend and frontend production build remain unverified unless separately run.

## Remaining risks

- SMTP remains at-least-once and cannot guarantee no duplicates after an ambiguous connection failure.
- Resend idempotency is limited to its provider retention window.
- Lease renewal occurs between recipients, not during a single provider request; provider timeout must remain well below the 15-minute lease.
- The worker lease coordinates this campaign worker only; it is not a general-purpose distributed job framework.
