# Video Content Studio and multi-platform roadmap

## Implemented in this milestone

- Added a brand-aware AI video-script endpoint for TikTok, Instagram Reels, Facebook Reels, YouTube Shorts, and long-form YouTube.
- Script inputs include topic, destination format, target duration, creative style, and optional call to action.
- Generated scripts request an opening hook, timestamped scenes, visuals, on-screen text, dialogue/voiceover, caption, platform title, description, hashtags, and recording notes.
- The prompt explicitly prohibits invented prices, product features, guarantees, results, and fabricated customer testimonials.
- Added a dedicated monthly `ai_video_scripts` usage metric and hourly abuse guard.
- Added a Video Script mode to the frontend Content Studio. Scripts can be edited and saved as drafts.
- Added YouTube to the social-provider directory. TikTok Login Kit OAuth and YouTube Google OAuth account-connection flows are implemented in code; their connect actions are enabled only when provider credentials and token encryption are configured. YouTube resumable video upload is also implemented in code and has a dedicated publishing page.

## Platform implementation sequence

1. Instagram professional-account OAuth and separate Facebook Page OAuth are implemented in code. Complete live configuration/testing and provider review before launch.
2. TikTok: Login Kit OAuth and encrypted account connection are implemented. Creator-info query, explicit consent, browser-to-TikTok chunk upload, automatic status polling, encrypted token refresh, and audit-aware privacy behavior are implemented as an initial foundation. Upload-session recovery and live provider verification remain outstanding. TikTok's current Direct Post API requires `video.publish`; unaudited clients are restricted to private-only publishing and have additional user limits. Do not promise public direct publishing until TikTok approves/audits the client.
3. YouTube: Google OAuth with OpenID identity, offline access, least-privilege `youtube.upload`, resumable video upload, privacy/metadata controls, and processing-status API are implemented in code. Channel identity is currently represented by the authorized Google identity; channel selection/verification and browser-closure recovery remain outstanding. Shorts use the YouTube video upload API; Shorts classification follows YouTube's platform rules rather than a separate upload endpoint.
4. Build shared media library, video file validation/transcoding, thumbnail support, scheduled publishing jobs, and per-platform publishing states.

## Not implemented / not verified

- TikTok OAuth and Direct Post, YouTube OAuth and resumable upload, and Facebook Page OAuth/text-link publishing are implemented in code but have not been live-tested against configured provider apps/accounts.
- No automatic video rendering, voice generation, editing timeline, transcoding, or media hosting is included yet. The current feature generates a production-ready script, not a finished video file.
- Platform API credentials, app reviews, OAuth redirect URLs, upload infrastructure, and provider-side approvals are required before live publishing.
- Frontend build and browser tests remain unverified until dependencies can be installed.
