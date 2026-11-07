# Social Integrations and Brand Intelligence

**Status:** Partially implemented. Instagram, Facebook Pages, TikTok and YouTube OAuth connection flows are implemented in code. Facebook text/link publishing, TikTok Direct Post, and YouTube resumable video upload workflows are implemented in code. None has been live-verified against production-like provider apps/accounts. Hybrid Brand Intelligence ingestion, analysis, evidence tracking and review remain unimplemented. The Video Content Studio generates scripts but does not render finished videos.

## Product behavior

1. The business owner must provide business name, industry, niche, offer, audience, and goals in onboarding. These remain the authoritative user-provided facts.
2. Connecting social accounts is optional. The dashboard and AI features must work when no account is connected or when an account has no accessible posts.
3. When authorized, sync at most the latest 20 accessible posts per connected account for the initial brand analysis. Respect provider pagination, scopes, rate limits, retention rules, and access restrictions.
4. Store social observations separately from user-confirmed profile facts. Each observation records provider, account, source post identifier, observed timestamp, sync timestamp, and confidence/provenance.
5. Analyze recurring topics, content categories, tone, writing patterns, recurring themes, hashtags, emoji use, and available engagement/posting patterns. Do not imply unavailable metrics were collected.
6. Present a reviewable proposed brand voice/profile. Never silently overwrite onboarding facts. Surface contradictions for owner/admin review.
7. Support disconnect, token revocation where available, deletion of imported post data, and periodic refresh. Never request or store social-media passwords; use provider OAuth only.

## Initial provider strategy

- **Instagram:** Support professional (Business/Creator) accounts only. Evaluate Instagram Login as the initial path; confirm the current permission set and app-review requirements in Meta's developer console before production. Personal consumer accounts are not supported by the professional-account APIs. Instagram Login and Facebook Login are different authorization configurations and must not have their scopes mixed.
- **TikTok:** Use Login Kit OAuth and request only approved scopes needed for profile and public video retrieval (for example `user.info.basic` and `video.list`). For video publishing use the Content Posting API and `video.publish`; implement creator-info query, privacy-level selection, explicit consent, upload, and publish-status polling. TikTok restricts unaudited Direct Post clients to private visibility and applies user/post caps; do not promise public direct publishing before audit approval.
- **LinkedIn:** Use three-legged OAuth. `w_member_social` is an open permission for member posting, but broader Marketing API access requires approval. Do not assume member post-history or analytics access is available merely because sign-in works.
- **Facebook Pages:** Treat as a separate provider connection and permission set; only implement after verifying the current Meta Page permissions and app review requirements.
- **YouTube:** Use Google OAuth with the `youtube.upload` scope, identify the authorized channel, and upload through the YouTube Data API `videos.insert` resumable-media flow. Respect quota limits, privacy selection, processing status, and API verification requirements. Shorts use the normal video upload endpoint; there is no separate Shorts upload API.

## Security and implementation requirements

- OAuth authorization-code flow with exact redirect URI allowlists, cryptographically random single-use state, expiry, and PKCE wherever the provider supports/requires it.
- Validate state on callback and bind it to the initiating user and organization. Never accept organization IDs from an untrusted callback parameter as authority.
- Keep client secrets and provider tokens server-side. Encrypt tokens at rest using a dedicated production encryption key separate from `SECRET_KEY`; never log tokens or return them to the browser.
- Persist provider, provider account ID, display name/handle, granted scopes, token expiry, connection status, last sync time, and revocation/disconnection timestamps.
- Enforce tenant authorization on every connection and sync route. Only owner/admin may connect or disconnect accounts; members may view connection status if permitted by product roles.
- Use provider-specific adapters behind a shared interface. Handle token refresh, revoked/expired tokens, rate limits, transient errors, and partial pagination explicitly.
- Use durable sync jobs and idempotent upserts before enabling recurring background sync. Do not run long provider syncs inside web requests.
- Do not scrape websites or use unofficial endpoints. Do not claim a connection or sync succeeded until the provider confirms it.

## Delivery sequence

1. Confirm developer-app registration, provider product access, callback domains, scopes, app-review requirements, and environment secrets.
2. Implement encrypted connection records, OAuth state/PKCE, connect/callback/disconnect endpoints, and provider capability metadata.
3. Implement frontend connection center with truthful per-provider availability/status and consent explanations.
4. Implement one provider adapter at a time, beginning with the provider whose app approval and test account are ready.
5. Add sync job records, post normalization, latest-20 import, retry/rate-limit handling, and deletion controls.
6. Implement brand analysis and review UI, with explicit provenance/confidence and user confirmation.
7. Test OAuth callbacks, tenant isolation, token encryption, revocation, provider failures, no-post accounts, and conflicting brand observations.

## Current provider references

- Meta Instagram API overview: https://developers.facebook.com/docs/instagram-platform/overview
- TikTok scopes: https://developers.tiktok.com/doc/scopes-overview
- TikTok Display API getting started: https://developers.tiktok.com/doc/display-api-get-started
- TikTok token management: https://developers.tiktok.com/doc/login-kit-manage-user-access-tokens
- TikTok Content Posting API Direct Post: https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- TikTok Content Sharing Guidelines: https://developers.tiktok.com/docs/en/content-sharing-guidelines
- YouTube video upload API: https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
- YouTube Data API quota overview: https://developers.google.com/youtube/data/getting-started
- LinkedIn API access and permissions: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- LinkedIn OAuth overview: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication

Provider APIs, scopes, eligibility, and app-review requirements change. Re-check official provider documentation and the app's actual granted permissions immediately before implementing and deploying each adapter.

## Implementation progress — social account foundation

Implemented in milestone 1:
- Organization-scoped `social_accounts` metadata table and migration `20261102_0008`.
- Authenticated provider registry endpoint: `GET /organizations/{organization_id}/social-accounts/providers`.
- Authenticated account inventory endpoint: `GET /organizations/{organization_id}/social-accounts`.
- Owner/admin disconnect endpoint: `DELETE /organizations/{organization_id}/social-accounts/{account_id}`.
- Frontend Social Accounts page at `/social-accounts`, linked from the dashboard, with provider readiness, connected-account inventory and disconnect UI.
- Tenant isolation and role checks covered by automated tests.

Still not implemented: provider API synchronization, post ingestion, content analysis, and brand profile approval. Instagram, Facebook Pages, TikTok and YouTube have provider-specific OAuth callbacks and encrypted credential storage in code. Provider readiness depends on the corresponding credentials, redirect URL and encryption key being configured; configured readiness is not proof of live provider approval or successful production operation. Do not present an account as connected until a verified OAuth callback creates its account record.

## Meta OAuth implementation milestone (2026-11-02)

Implemented the first real provider path: **Instagram API with Instagram Login** for Instagram professional accounts. This is intentionally distinct from Facebook Login/Page authorization; a Facebook Page is not silently marked as connected by this Instagram flow.

- `POST /organizations/{organization_id}/social-accounts/instagram/connect` is owner/admin-only, creates a random one-time state value (only its SHA-256 digest is stored), binds it to the user and organization, applies a short expiry, and returns Meta's authorization URL.
- `GET /social-oauth/meta/instagram/callback` consumes state once, exchanges the authorization code server-side, exchanges the short-lived token for a long-lived token, fetches the professional account identity, and persists the account.
- Access tokens are encrypted with Fernet before database storage. They are never returned to the browser or included in account inventory responses. The encryption key is independent of `SECRET_KEY`.
- Instagram and Facebook Page readiness are evaluated separately and require Meta app credentials, the corresponding redirect URI and encryption key. LinkedIn remains unavailable because its OAuth integration is not implemented; YouTube readiness depends on Google OAuth configuration.
- Disconnect removes the account and its credential via the database foreign-key cascade.
- `backend/.env.example` documents Meta settings and key generation. Configure the exact callback URL in Meta's developer dashboard and use HTTPS in production.

### External setup and limits

Create/configure a Meta app with the Instagram Login product, register the exact callback URL, and request the minimum `instagram_business_basic` permission for the initial profile connection. Instagram Login is for professional accounts (Business or Creator); personal accounts are not supported. Meta app review/advanced access may be required before serving accounts beyond app roles/testers. Live OAuth cannot be verified until real Meta app credentials and a public callback URL are supplied/configured.

Official reference material reviewed: Meta's Instagram API collection documents Instagram Login and the professional-account model; Meta's permissions reference explains app review and advanced access. See https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api and https://developers.facebook.com/docs/permissions/reference/.

### Remaining work

- Facebook Page connection is a separate Facebook Login for Business flow, including cursor-based Page discovery and Page access token management; implemented in code but not live-verified.
- Refresh-token/long-lived-token maintenance, revocation/deauthorization webhook handling, periodic sync and account data deletion workflows remain future work.
- Provider OAuth app review, privacy policy/data deletion URLs and production secrets must be completed before public launch.


## Video Content Studio progress (2026-11-02)

- AI video-script generation is implemented for TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, and long-form YouTube.
- TikTok and YouTube appear in the provider registry. Their Connect actions are enabled only when server-side credentials and encryption are configured. Script generation does not imply video publishing capability.
- TikTok Direct Post requires explicit user consent and creator-info-driven privacy choices; unaudited API clients are private-only and limited. See the official TikTok Content Posting API and sharing guidelines.
- YouTube video upload uses `videos.insert` with OAuth and resumable media; quota and privacy status must be respected.
- See `docs/video-content-studio.md` for the feature boundary and remaining work.


## TikTok Login Kit — implemented foundation

The backend now supports TikTok web OAuth using Login Kit: a one-time, hashed state bound to the initiating organization/user, server-side authorization-code exchange, account identity lookup, encrypted access/refresh-token storage, and account disconnect through the shared social-account API. The frontend exposes a TikTok Connect action only when server-side credentials and token encryption are configured. Requested scopes are `user.info.basic`, `video.list`, and `video.publish`; `video.list` is needed for Brand Intelligence retrieval and `video.publish` is needed for publishing. Each scope must be enabled/approved for the developer app and granted by the user. Existing TikTok connections must reconnect to grant newly added `video.list`.

TikTok Direct Post is also implemented in code: the backend queries creator information before each post, requires explicit consent, applies creator privacy/interaction settings, initializes FILE_UPLOAD sessions, persists publish tracking and exposes provider status. The browser transfers chunks directly to TikTok. Unaudited clients are restricted to private-only visibility. Live provider verification, durable upload-session recovery, and a shared scheduled-publishing engine remain outstanding.

Configuration: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`, `TIKTOK_FRONTEND_RETURN_URL`, and `SOCIAL_TOKEN_ENCRYPTION_KEY`. Never expose client secrets or access/refresh tokens to the browser.


### YouTube Google OAuth — connection foundation

YouTube account authorization uses Google's server-side OAuth code flow with a hashed, one-time state tied to the organization and initiating user. It requests OpenID identity and the narrow `youtube.upload` scope, uses offline access, and encrypts access and refresh tokens in the shared credential store. The callback verifies the Google account through the OpenID userinfo endpoint. Resumable `videos.insert` upload, upload-ID verification, and processing-status checks are implemented in code. Explicit channel selection for Google identities with multiple channels and browser-closure recovery remain outstanding.

### TikTok publishing reliability

The TikTok publishing page automatically polls provider status while a job remains active. The backend attempts access-token refresh shortly before expiry and stores rotated tokens encrypted. A failed/interrupted browser-to-provider upload currently requires starting a new upload session; durable recovery is not implemented.

## Facebook Pages integration

Facebook Page Login is implemented as a separate Meta OAuth flow from Instagram Login. It requests `pages_show_list`, `pages_read_engagement`, and `pages_manage_posts`, exchanges the authorization code and short-lived user token server-side, discovers Pages through `/me/accounts`, and encrypts each eligible Page access token in the existing social credential store. Page records are organization-scoped. The first publishing surface supports text and optional link posts through `/{page-id}/feed`; it also supports Meta-native scheduled text/link posts. Personal profile publishing is not supported. Photo/video publishing and broader unified cross-platform scheduling remain future work. Production use with customer-owned Pages requires the relevant Meta App Review/Advanced Access and business verification where Meta requires it.

Configuration: `META_APP_ID`, `META_APP_SECRET`, `SOCIAL_TOKEN_ENCRYPTION_KEY`, `FACEBOOK_REDIRECT_URI`, and `FACEBOOK_FRONTEND_RETURN_URL`. Facebook callback path: `/api/v1/social-oauth/facebook/callback`.


## Audit clarification — 2026-11-02

The provider connection/publishing code now includes transactional activity logging. Facebook Page discovery follows cursor pagination and will not report success unless at least one Page has the `CREATE_CONTENT` task. These code-level safeguards are covered by mocked tests; they do not replace live Meta/TikTok/Google verification.

## Brand intelligence backend slice — 2026-11-04

Added organization-scoped `social_post_observations` and `brand_intelligence_analyses` tables (migration `20261104_0027`). The API can list observations, accept explicitly unverified manual observations, analyze up to 20 stored observations into a structured pending proposal, list proposals, record owner/admin approval or rejection, and delete observations. Analysis preserves source observation IDs, model provenance, and reported conflicts. It never writes social-derived content into the confirmed business profile. See `docs/brand-intelligence-api.md` for the contract.

**Not yet complete:** official provider adapters for post-history retrieval, automatic latest-20 synchronization, durable sync jobs/retries, provider-specific scopes/app-review verification, frontend review experience, and live AI/provider tests. Manual observations are a development/review bridge only and must not be represented as automatic social sync.


### TikTok Brand Intelligence retrieval
The backend now uses TikTok's official `POST /v2/video/list/` endpoint when a connected account has the `video.list` scope. Up to 20 recent videos are normalized into the shared observation model (video ID, description/title, share URL, creation time, and media type). This is user-triggered synchronization, not a scheduled background job. Live API/app-scope approval and refresh-token behavior still require verification.
