# TikTok Content Posting API

## Implemented foundation

- Fetches current creator information from `POST /v2/post/publish/creator_info/query/` before initializing a Direct Post.
- Displays the creator nickname, uses the provider's privacy options, respects disabled interaction settings, and checks the creator's maximum video duration.
- Requires explicit user consent before initializing a post.
- Initializes `FILE_UPLOAD` Direct Post sessions through `POST /v2/post/publish/video/init/`.
- The browser sends video chunks directly to TikTok's short-lived upload URL. The BizPilot Pro API does not receive the media bytes or return the user's OAuth access token.
- Persists the TikTok `publish_id` and organization/account-scoped status record.
- Fetches provider status using `POST /v2/post/publish/status/fetch/`; only `PUBLISH_COMPLETE` is shown as published.
- Uses conservative 10 MiB chunks and a 1 GiB application upload limit.

## Audit and privacy guard

`TIKTOK_CONTENT_POSTING_AUDITED` defaults to `false`. While false, the backend accepts only `SELF_ONLY` even if the creator endpoint returns additional privacy levels. Change it to `true` only after the TikTok Content Posting API client has passed TikTok's audit and the product's UX has been reviewed against current guidelines. Never use this flag to bypass TikTok's review.

## Required TikTok app setup

1. Add the Content Posting API product to the TikTok developer app.
2. Request and obtain approval for `video.publish`.
3. Ensure each creator grants `video.publish` in OAuth.
4. Complete TikTok's Direct Post audit before enabling non-private visibility.
5. Test the app using TikTok's sandbox/test environment and production callback configuration.

## API routes

- `GET /api/v1/organizations/{organization_id}/tiktok/accounts/{account_id}/creator-info`
- `POST /api/v1/organizations/{organization_id}/tiktok/accounts/{account_id}/direct-post`
- `GET /api/v1/organizations/{organization_id}/tiktok/publish-jobs/{job_id}`

The direct-post response contains an ephemeral TikTok upload URL. Treat it as a bearer upload credential: do not log it, persist it in application records, or share it beyond the authenticated browser session. The browser uploads sequential chunks with `Content-Range` and `Content-Type`.

## Remaining work / limitations

- The browser upload path and status refresh are synchronous/manual; background polling, retry/resume, and durable upload recovery are not implemented.
- A failed chunk currently requires starting a new TikTok upload session.
- Token refresh/rotation and automatic reconnect UX remain to be implemented. Expired or revoked credentials require reconnecting.
- The API and browser workflow have not been exercised against a live TikTok developer app. Provider approval, CORS behavior for upload URLs, account-specific limits, and app audit remain external validation tasks.
- The frontend dependencies are not installed in this build environment; Next.js typecheck/build/browser tests remain unverified.
