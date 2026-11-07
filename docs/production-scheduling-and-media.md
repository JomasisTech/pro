# Production scheduling and media operations

## Scheduled worker

The API starts the database-backed scheduled-post worker when `SCHEDULER_WORKER_ENABLED=true`.
The worker polls every `SCHEDULER_POLL_INTERVAL_SECONDS` (minimum 5 seconds), uses its own
SQLAlchemy sessions, and relies on atomic database claims so concurrent dispatch cycles do not
claim the same scheduled row. The Render blueprint enables this worker in the API service.

Keep the Render service at one instance while media is stored on its attached persistent disk.
The disk is mounted at `/var/data`, and `MEDIA_STORAGE_DIR=/var/data/media` keeps uploads across
service restarts and deployments. Do not scale this service horizontally with local-disk media: a
second instance would not see the first instance's files. Before horizontal scaling, implement a
shared S3-compatible object-storage adapter and migrate existing media objects.

## TikTok consent

TikTok scheduled-post creation requires `consent_to_upload=true` at the API boundary. The
backend persists the consent boolean, UTC timestamp, and consent text version. The dispatcher
rechecks those fields immediately before sending the video to TikTok. The frontend checkbox is
only a user-interface aid; it is not the security or compliance boundary.

## Retry and recovery

The dispatcher counts a new queued publish attempt separately from provider status polling.
Publishing-status checks therefore do not consume the upload retry budget. If TikTok reports a
definitively failed publish session, its ID is cleared before the bounded retry. If a worker
restarts and TikTok reports `PROCESSING_UPLOAD`, the incomplete session is abandoned and a fresh
session is scheduled; `PROCESSING_DOWNLOAD` and other in-progress states are polled instead.
Processing leases are currently 60 minutes to accommodate long video transfers.

The worker cannot guarantee exactly-once publishing across an ambiguous network failure after a
provider accepts a post. It reconciles provider status wherever a publish ID exists; operational
monitoring and manual review remain necessary for provider states that cannot be reconciled.

## Brand Intelligence synchronization worker

The same `SCHEDULER_WORKER_ENABLED=true` switch starts a database-backed Brand Intelligence worker alongside the scheduled-post dispatcher. It processes queued jobs from `brand_sync_jobs`, and automatically queues connected social accounts that have never synchronized or whose last successful sync is at least six hours old. Each sync still retrieves at most the latest 20 provider items. The API exposes `POST /api/v1/organizations/{organization_id}/brand-intelligence/sync-jobs/{social_account_id}` (202 Accepted), `GET .../sync-jobs`, and `GET .../sync-jobs/{job_id}`. The existing synchronous `/sync/{social_account_id}` endpoint remains available for manual immediate synchronization.

Jobs are persisted in PostgreSQL, deduplicated while queued/running, and retried up to three attempts for server/provider failures with 1- then 2-minute backoff. Permission, disconnected-account, and other client errors are terminal and visible in the job status. A job left `running` for more than 30 minutes is recovered on a worker cycle; after exhausting attempts it becomes failed. Automatic scheduling is limited to at most one new scheduled attempt per connected account per six hours. The worker writes activity-log entries for automatically queued jobs and the sync operation itself.

Enable `SCHEDULER_WORKER_ENABLED=true` only after applying migrations through `20261104_0028`. Keep the current single-instance deployment topology; this worker uses database conditional claims but does not yet provide a distributed lease/heartbeat for long-running provider calls. Live provider, PostgreSQL concurrency, and production worker supervision tests remain required.
