# TikTok background video transfer — implementation contract

## Current status

The backend now supports scheduling a TikTok Direct Post video from an organization-owned media asset. The scheduling API validates the account scope and tenant ownership of the asset. The dispatcher initializes a fresh Direct Post session at execution time, checks creator privacy and duration constraints, uploads the stored file, persists TikTok's `publish_id`, and polls the status on later dispatcher runs until TikTok reports completion or failure. The backend has a tested transfer primitive at `app.modules.posting.tiktok_upload.upload_video_file`. It accepts a freshly initialized TikTok Direct Post upload URL, a local stored media path, and a supported video content type (`video/mp4`, `video/quicktime`, or `video/webm`). It sends sequential HTTP PUT requests with `Content-Length` and `Content-Range` headers and returns the total number of bytes transferred.

## Provider sequence required for the future worker

1. At the scheduled execution time, load the organization-owned media asset and verify its file exists and its size matches the recorded metadata.
2. Obtain/refresh the connected TikTok account token and query creator information. Enforce the creator's current privacy options and duration limits; unaudited apps must remain `SELF_ONLY`.
3. Initialize `/v2/post/publish/video/init/` with `source=FILE_UPLOAD`, media size, chunk size, total chunk count, caption, and user-selected post settings.
4. Validate the returned upload URL and immediately call `upload_video_file`. Never store or reuse the URL for a future scheduled execution; TikTok documents a one-hour expiry.
5. Persist the returned `publish_id`, then poll `/v2/post/publish/status/fetch/` with bounded backoff until a terminal status is reached. Record provider status and activity history.
6. On a failed/expired transfer, create a new provider upload session only when it is safe to retry. A timeout after TikTok accepted the final chunk can be ambiguous; reconcile by checking status before starting a duplicate publish.

## Security and operational constraints

- The upload helper only permits HTTPS to `open-upload.tiktokapis.com`, requires a query string, rejects embedded URL credentials, and disables HTTP redirects.
- Media remains in private organization-owned storage; provider access tokens are not sent to the browser.
- The helper uses bounded sequential chunks and never loads the entire video into memory.
- Tests use `httpx.MockTransport`; no live provider call has been made.
- The worker is now wired to the scheduling API. Create a TikTok schedule with `provider=tiktok`, `media_asset_id`, `video_duration_seconds`, `privacy_level`, and optional interaction flags. The media asset must belong to the same organization and be an MP4, QuickTime, or WebM file. The API requires the `video.publish` scope. The worker shares the configured media storage volume with the API process. The frontend scheduling form is not yet connected to this API. Live TikTok provider behavior and PostgreSQL migration execution remain unverified.

## API contract example

```json
{
  "social_account_id": "<connected-account-uuid>",
  "provider": "tiktok",
  "title": "Behind the scenes",
  "content": "A short video caption",
  "media_asset_id": "<organization-owned-media-asset-uuid>",
  "video_duration_seconds": 24,
  "privacy_level": "SELF_ONLY",
  "allow_comment": true,
  "allow_duet": false,
  "allow_stitch": false,
  "scheduled_at": "2026-12-01T10:00:00+01:00"
}
```

The dispatcher must be invoked periodically (for example, once per minute). A job in `publishing` state is polled on subsequent runs; it is not uploaded again while a `publish_id` exists. The unaudited-client privacy restriction is enforced by allowing only `SELF_ONLY` unless `TIKTOK_CONTENT_POSTING_AUDITED=true`.

## Official references

- [TikTok Direct Post API](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post)
- [TikTok Media Transfer Guide](https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide)


## Frontend scheduled publishing flow

The `/schedule-post` page now supports Facebook Page posts and TikTok video schedules. For TikTok, the browser:

1. Loads connected TikTok accounts and creator settings.
2. Collects the video, caption, privacy selection, interaction preferences, explicit consent, and scheduled time.
3. Uploads the raw video body to the authenticated organization media-assets endpoint (not to TikTok).
4. Sends the returned `media_asset_id`, duration, creator settings, and timezone-aware `scheduled_at` to the shared scheduled-post API.

The media upload is organization-private and requires an owner/admin role. The scheduling endpoint independently checks account permission and media-asset organization ownership. The worker later sends the video to TikTok when due. The frontend currently enforces the configured 1 GiB default upload ceiling; the backend remains authoritative.
