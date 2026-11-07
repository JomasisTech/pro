# Follow-up remediation — renewable scheduler leases

**Date:** 2026-11-04  
**Baseline:** BizPilotPro v0.2.7 post-report patch  
**Scope:** Scheduler lease renewal and stale-worker ownership protection.

## Implemented

- Added nullable `lease_token` (UUID) and `lease_expires_at` columns to `scheduled_posts` in migration `20261104_0022`.
- Each dispatcher claim assigns a fresh token and a 60-minute expiry.
- A daemon heartbeat thread uses its own SQLAlchemy session to renew the lease every 30 seconds, conditional on both job ID and lease token still matching and status remaining `processing`.
- Expired lease recovery uses `lease_expires_at`, with a fallback to `processing_started_at` for rows created before the migration.
- The dispatcher checks ownership before recording provider success and before writing retry/failure state. A worker that no longer owns the token does not overwrite the current database state.

## Verification

- `python -m compileall -q app tests`: passed.
- `DATABASE_URL=sqlite:////tmp/bizpilot-test2.db python -m pytest -q`: **190 passed, 2 skipped**.
- `DATABASE_URL=sqlite:////tmp/bizpilot-migrate.db alembic upgrade head`: passed through `20261104_0022`.

## Limitations

- SQLite verification does not establish PostgreSQL locking or concurrent-worker behavior.
- A lost lease during an external provider request cannot undo a post already accepted by the provider. Provider idempotency/reconciliation remains a separate requirement.
- The heartbeat intentionally stops on a database renewal error; the job remains subject to expiry recovery. Operational alerting for repeated heartbeat failures is not yet implemented.
