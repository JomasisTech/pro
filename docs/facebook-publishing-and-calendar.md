# Facebook publishing and content calendar

## Implemented in code
- Facebook Pages OAuth with one-time state bound to the initiating user and organization.
- Cursor-based Page discovery through Meta Graph API `/me/accounts`; eligible Page access tokens are encrypted server-side.
- Text and optional link publishing to `/{page-id}/feed`.
- Meta-native scheduled publishing using `published=false` and `scheduled_publish_time` (10 minutes to 30 days validation in this implementation).
- `/facebook-publish` frontend composer.
- `/calendar` unified feed combining saved drafts, Facebook provider-backed scheduled/published entries, and TikTok/YouTube publishing-job history.
- Transactional activity logging for successful Facebook publishing/scheduling and Facebook Page connections.
- Date-scoped calendar queries include immediate posts by filtering on `scheduled_at` or, when absent, `created_at`.

## Boundaries and verification
- Facebook personal profiles and Groups are not supported.
- Photo/video/Reels publishing is not included.
- BizPilot Pro runs a shared database-backed dispatcher for Facebook Page text/link posts and Instagram professional-account single-photo posts. Run it periodically with `python -m app.modules.posting.dispatcher`.
- The calendar UI provides month, week, and 30-day agenda views. The API feed includes saved drafts, Facebook calendar entries, and TikTok/YouTube publishing jobs. TikTok and YouTube jobs are displayed as upload/publishing history using their creation timestamp; they are not scheduled posts.
- Cross-platform scheduling/dispatch, provider-side cancellation/rescheduling, post synchronization, and publishing-history recovery are not implemented.
- Meta App Review/Advanced Access and business verification may be required before customer accounts can authorize these permissions. Live OAuth and publishing remain unverified.

## API
- `POST /api/v1/organizations/{organization_id}/social-accounts/facebook/connect`
- `GET /api/v1/social-oauth/facebook/callback`
- `POST /api/v1/organizations/{organization_id}/facebook/publish`
- `GET /api/v1/organizations/{organization_id}/calendar`

## Calendar persistence
Successful Facebook posts and scheduled posts are recorded in `calendar_entries` and returned alongside saved drafts. Immediate posts have no scheduled timestamp; their creation time is used for date filtering and display. The calendar currently aggregates Facebook only for provider-backed events.


## TikTok and YouTube calendar aggregation

The organization-scoped `GET /calendar` endpoint includes `tiktok_publish_jobs` and `youtube_publish_jobs` in addition to drafts and Facebook `calendar_entries`. TikTok items expose the caption and provider `publish_id`; YouTube items expose the title, description, and video ID when available. Both use `created_at` as the calendar timestamp and return `scheduled_at: null`. Date filters apply to each job's creation timestamp. This represents upload/publishing activity only; neither provider currently supports scheduling through BizPilot Pro's shared scheduler.


## Instagram scheduled photo publishing

The shared scheduler now accepts Instagram professional accounts when the connection records both `instagram_business_basic` and `instagram_business_content_publish`. Instagram Login requests both permissions. Scheduled Instagram items require a public HTTPS `media_url`; the worker creates an image media container and then calls `media_publish`. Captions are stored in the shared `content` field. This slice supports single-image photo posts only: carousels, Reels, Stories, video uploads, alt text, and provider-side cancellation/rescheduling are not included. The media URL must remain fetchable by Meta until the worker processes the job. OAuth scope approval, public media hosting, and live publishing still require verification with an approved Meta app and professional test account.


## Dispatcher reliability

Scheduled jobs use a processing lease so jobs left in `processing` by a crashed worker can be reclaimed after 15 minutes. Transient failures are retried with exponential backoff (1, 2, then up to 60 minutes), with a maximum of three attempts. A job is marked failed after its final attempt. The dispatcher remains an externally-run process; production process supervision and operational monitoring are still required.
