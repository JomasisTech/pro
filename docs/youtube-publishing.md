# YouTube video publishing

BizPilot Pro now has a YouTube Data API upload foundation and a browser publishing page at `/youtube-publish`.

## Flow

1. Connect a Google account with the `youtube.upload` OAuth scope.
2. Select the authorized Google account, choose a local video file, enter title/description/tags, choose visibility, and declare whether it is made for kids. The Google authorization determines the destination YouTube channel; explicit channel switching for accounts with multiple channels is not implemented yet.
3. Confirm consent. The backend validates organization ownership, connected-account state, upload scope and token validity; refreshes expired Google access tokens server-side; then creates a YouTube resumable-upload session.
4. The browser uploads 8 MiB chunks directly to Google's HTTPS session URL. It follows the `308 Resume Incomplete` Range response and probes the session after retryable network failures.
5. The browser submits the returned video ID to the backend. The backend verifies the ID against the connected account before recording it.
6. Status checks read YouTube's `status` and `processingDetails`. BizPilot Pro only marks a video complete after YouTube reports successful processing; failed/rejected states remain failures.

The resumable session URL is encrypted at rest and is a bearer-like capability, so it must be treated as secret. It is returned only to the authenticated owner/admin who starts the upload. OAuth access/refresh tokens never go to the browser.

## Current limitations / production checklist

- The protocol handles short transient network failures automatically. A full user-facing recovery flow after the browser is closed or retries are exhausted is not implemented yet, even though the session URL is encrypted in the database. A later milestone should add an authenticated resume endpoint and reselected-file byte-range verification UX.
- No background worker polls YouTube while the user is away; status is checked by the active page or on demand.
- Google OAuth consent-screen verification, YouTube API quota, channel permissions and real provider uploads have not been live-tested. Public uploads may be subject to Google's API audit/verification restrictions.
- The API does not transcode videos. YouTube decides whether an eligible vertical/square video is classified as a Short; BizPilot Pro does not force a Shorts flag.
- The current browser-to-Google upload flow relies on Google's resumable upload endpoint supporting browser CORS. Test against the deployed production origin before launch.

## Configuration

Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YOUTUBE_REDIRECT_URI`, `YOUTUBE_FRONTEND_RETURN_URL`, and `SOCIAL_TOKEN_ENCRYPTION_KEY`. Use an HTTPS callback URI for deployed environments. Do not commit credentials.

## Official references

- [YouTube videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- [Resumable upload protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol)
- [Video resource and processing status](https://developers.google.com/youtube/v3/docs/videos)
