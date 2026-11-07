# Google sign-in setup

AutoBizPro currently offers Google as its first external identity provider. It requests only `openid email profile` and does not request access to Gmail, Drive, YouTube, or other Google services.

## Google Cloud setup

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select the project used by AutoBizPro (or create one).
2. Configure the OAuth consent screen / Google Auth Platform branding, audience, and contact details.
3. Create an OAuth client with application type **Web application**.
4. Add the exact authorized redirect URI `https://YOUR_API_HOST/api/v1/auth/google/callback` (for local development: `http://localhost:8000/api/v1/auth/google/callback`).
5. Set `GOOGLE_LOGIN_CLIENT_ID` and `GOOGLE_LOGIN_CLIENT_SECRET` in the backend environment. Set `GOOGLE_LOGIN_REDIRECT_URI` to the exact redirect URI registered above and `GOOGLE_LOGIN_FRONTEND_RETURN_URL` to `https://YOUR_FRONTEND_HOST/auth/callback`.
6. Run the Alembic migration: `alembic upgrade head`.
7. Set the OAuth consent screen to Production and complete Google's verification requirements before public launch if Google requires verification for your app/audience.

The login callback validates the authorization state cookie, Google ID-token signature, issuer, audience, expiry, verified email, and OIDC nonce. Provider identities are stored by Google's stable `sub` identifier, not by email alone. If the Google email matches an existing account that was created by Google sign-in, the same account is used. If it matches an account that was registered with a password, **it is not linked** and the person is sent back to the login page with a message to sign in with their password: email verification is not implemented yet, so we cannot be sure whoever registered that email actually owns it (linking would let that person's password reach the real owner's Google account). Revisit this once email verification exists.

## Local development

Use the localhost redirect URI above and add it to the OAuth client. Browser and API must use the same host spelling (`localhost` vs `127.0.0.1`) so the state cookie is sent to the callback.

## Scope of this release

Google sign-in is implemented. WhatsApp is available as a one-time-code sign-in (see `whatsapp-sign-in.md`); it is not an OAuth identity provider. Facebook, Apple and Microsoft/Outlook are not enabled. Microsoft sign-in can be considered next if customer demand warrants Azure app registration. Do not expose client secrets in frontend environment variables.

## Behaviour notes

- `GET /api/v1/auth/providers` reports which social options are configured; the login/register pages only show buttons that will work.
- If Google is not configured, `GET /api/v1/auth/google` redirects to `/login?social_error=google_unavailable` instead of returning raw JSON.
- Accounts created by Google sign-in have no password (`has_password = false`) and a workspace named "<name>'s Workspace". The dashboard prompts the owner to add their business details (non-blocking).
