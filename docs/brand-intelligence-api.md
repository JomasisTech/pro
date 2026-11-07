# Brand Intelligence API — first backend slice

All endpoints are organization-scoped under `/api/v1/organizations/{organization_id}/brand-intelligence`.

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/observations` | Member | List the latest 100 stored observations |
| POST | `/observations/manual` | Owner/admin | Add or update a manually supplied post observation |
| POST | `/sync/{social_account_id}` | Owner/admin | Synchronously fetch and upsert up to 20 recent items (compatibility/diagnostic endpoint) |
| POST | `/sync-jobs/{social_account_id}` | Owner/admin | Queue a durable synchronization job; returns the existing active job when one is already queued/running |
| GET | `/sync-jobs` | Member | List the latest 50 jobs for the active organization |
| GET | `/sync-jobs/{job_id}` | Member | Read one job belonging to the active organization |
| POST | `/analyze` | Owner/admin | Analyze up to the latest 20 stored observations into a pending proposal |
| GET | `/analyses` | Member | List recent proposals and their review state |
| POST | `/analyses/{analysis_id}/review` | Owner/admin | Approve or reject a pending proposal |
| DELETE | `/observations` | Owner/admin | Delete imported/manual observations for the organization |

Manual observations are explicitly marked `method=manual` and `confidence=unverified`. They are not evidence of a provider API sync. Provider sync currently supports Instagram Login and Facebook Pages. Each adapter fetches at most 20 recent posts, upserts by `(social_account_id, source_post_id)`, updates `last_synced_at`, and writes an activity event. Instagram uses its long-lived-token refresh helper; Facebook uses the Page access token returned by the separate Facebook Page OAuth flow and requires both `pages_show_list` and `pages_read_engagement`. Provider provenance and available media type, caption/message, permalink, and timestamp are stored. The API supports both a synchronous compatibility endpoint and durable job endpoints. The frontend queues jobs and polls active job state every five seconds. A worker schedules due connected accounts every six hours, retries transient server/provider failures up to three attempts, and recovers stale running jobs. Instagram, Facebook, TikTok, and YouTube adapters are implemented, subject to their provider-specific read scopes. Worker supervision, live provider behavior, and PostgreSQL concurrency remain operational verification requirements.

Analysis uses the configured AI provider and stores a structured proposal, model name, source observation IDs, and conflicts. The proposal is never copied into `business_profiles`; owner/admin review is recorded as a separate decision. User-confirmed business facts remain authoritative.

All reads and writes are tenant-scoped. Mutations write activity-log entries in the same database transaction. Social-account deletion cascades observations; organization deletion cascades both observations and analyses.

## How approved analysis is used by AI content generation (Increment 31)

Caption and video-script generation read the most recently reviewed `approved` analysis for the active organization. Pending and rejected analyses are never included. The workspace profile's `brand_voice_mode` controls whether approved social-derived voice observations are used (`automatic` and `hybrid`) or ignored (`manual`). Owner-defined tone/phrase preferences and `custom_ai_instructions` remain explicit controls; in hybrid mode they are supplied alongside approved social observations. No analysis proposal is automatically copied into the business profile.
