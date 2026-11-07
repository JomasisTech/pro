# BizPilot Pro remediation update — 0.2.0

## Implemented in this update

- Added a configurable in-process scheduled-post worker, enabled in the Render blueprint.
- Added a 10 GB Render persistent disk for local media and configured `MEDIA_STORAGE_DIR` to use it.
- Added backend-enforced TikTok scheduling consent and persisted consent timestamp/version.
- Rechecked persisted consent immediately before TikTok upload.
- Enforced TikTok's 2,200-character caption limit at the scheduling API.
- Separated new queued publish attempts from TikTok status polling so status checks do not exhaust the retry budget.
- Added recovery for interrupted TikTok upload sessions and clearing of definitively failed provider sessions before retry.
- Extended abandoned-processing lease duration to 60 minutes.
- Added basic video container signature checks to reject obvious MIME-type spoofing.
- Updated backend/frontend package versions to 0.2.0 and documented deployment constraints.

## Verification

- Python compilation: passed.
- Backend test suite with an in-memory SQLite test database: 147 passed, 1 skipped.
- Alembic upgrade to revision `20261102_0019`: passed on SQLite.
- Alembic downgrade to `20261102_0018` and re-upgrade to head: passed on SQLite.
- Render YAML parsing: passed.
- Frontend lint and production build: not run; frontend dependencies are not installed and no lockfile is present in the supplied archive. Network access was unavailable to install them.
- PostgreSQL 16 migration verification and live TikTok publishing: still require deployment/test credentials and a real PostgreSQL/TikTok environment.

## Remaining production work

- Move media from local persistent disk to shared S3-compatible object storage before horizontal scaling or separating the worker into another service.
- Add renewable worker lease heartbeats for unusually long-running transfers.
- Add media cleanup/retention and orphan reconciliation.
- Add distributed rate limiting, account recovery/email verification, and billing lifecycle.
- Add end-to-end browser tests and live provider integration tests.
- Generate and commit a frontend package lockfile in a network-enabled development environment, then run lint/build.

## Deployment notes

1. Deploy the backend and apply migrations through `20261102_0019` (`alembic upgrade head`).
2. The Render blueprint enables the worker in the API process and mounts persistent media storage at `/var/data`.
3. Keep the Render service at one instance while using local disk media. Do not horizontally scale this configuration.
4. Keep `TIKTOK_CONTENT_POSTING_AUDITED=false` until TikTok approves the app; unaudited publishing remains restricted to `SELF_ONLY`.
5. Verify `MEDIA_PUBLIC_BASE_URL`, token encryption, OAuth credentials, and database settings before enabling real scheduled posts.
