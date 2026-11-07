# Authentication API (initial implementation)

Base prefix: `/api/v1/auth`

## Register

`POST /api/v1/auth/register`

```json
{
  "email": "owner@example.com",
  "password": "use-a-long-unique-password",
  "full_name": "Example Owner",
  "organization_name": "Example Studio"
}
```

Creates a user, an organization, and an `owner` membership in one database transaction. Email addresses are normalized to lowercase. Passwords must be 8–128 characters. The response contains a short-lived bearer access token, the user profile, and the initial organization. It never returns the password or password hash.

## Login

`POST /api/v1/auth/login`

```json
{
  "email": "owner@example.com",
  "password": "use-a-long-unique-password"
}
```

Returns the same response shape as registration. Incorrect email/password combinations return a generic `401` response.

**Rate limiting:** after `LOGIN_MAX_FAILED_ATTEMPTS` (default 5) failed attempts for the same email from the same client address within `LOGIN_LOCKOUT_SECONDS` (default 900), further login attempts return `429` with a `Retry-After` header (seconds), even if the password is then correct. A successful login clears that email's counter.

**Behind a proxy:** set `TRUSTED_PROXY_COUNT` to the number of reverse proxies in front of the API so the real client address is read from the end of `X-Forwarded-For` (earlier entries can be forged and are ignored). Optionally set `LOGIN_IP_MAX_FAILED_ATTEMPTS` (0 = off) to also cap failures per address across all emails, which slows password spraying. A successful login does not clear the per-address counter. Unknown emails still run a dummy Argon2 check so response time does not reveal which emails exist.

**Production secret:** with `APP_ENV=production` the API refuses to start unless `SECRET_KEY` is set to a unique value of 32+ characters (`render.yaml` generates one).

## Current user

`GET /api/v1/auth/me`

Send the token in the `Authorization: Bearer <access_token>` header. Missing, invalid, or expired tokens are rejected.

## Logout and sessions

- `POST /api/v1/auth/logout` (bearer token) revokes the presented access token immediately. Other devices' tokens keep working. Revoked token ids are kept in `revoked_tokens` until the token would have expired anyway.
- `POST /api/v1/auth/logout-all` (bearer token) bumps the user's `token_version`, which ends every token issued before it, on every device.
- Access tokens now carry `jti` (unique id) and `ver` (the user's `token_version`). `get_current_user` rejects a token if its `ver` differs from the user's current value or its `jti` is revoked. Tokens issued before this change (no `jti`/`ver`) still work until they expire; logging out with one bumps `token_version` instead.

## Change password

`POST /api/v1/auth/change-password` (bearer token) with `{"current_password": "...", "new_password": "..."}`.

Verifies the current password (failed attempts are limited per user using the login limit settings, answering `429` with `Retry-After`), requires a different new password (8–128 characters), bumps `token_version` so every other session ends, invalidates unused reset links, emails a "password changed" notice, and returns the same body as login with a fresh token so the current session continues.

## Forgot / reset password

- `POST /api/v1/auth/forgot-password` with `{"email": "..."}` always answers `202` with the same message, whether or not the account exists or is active. For an active account it stores a hashed one-time token (256-bit random, SHA-256 hash only), invalidates earlier unused links, and emails `FRONTEND_BASE_URL/reset-password#token=<token>` after the response is sent. Requests are limited per email (`PASSWORD_RESET_MAX_REQUESTS` per `PASSWORD_RESET_WINDOW_SECONDS`, default 3 per hour) and per client address (10x that); excess requests answer `429`.
- `POST /api/v1/auth/reset-password` with `{"token": "...", "new_password": "..."}` sets the new password and ends every existing session. A token works once and expires after `PASSWORD_RESET_TTL_MINUTES` (default 30). Invalid, used, or expired tokens all answer the same `400`. A weak password (`422`) does not consume the token. The reset does not sign the user in.

**Email delivery:** configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_STARTTLS`, and `EMAIL_FROM`. With `SMTP_HOST` empty and `APP_ENV` not `production`, the email (including the reset link) is written to the server log for local development. In production, nothing is sent and an error is logged; production also refuses to send reset links unless `FRONTEND_BASE_URL` is HTTPS.

## Current implementation notes

- Passwords are hashed with Argon2id (argon2-cffi). Older PBKDF2-SHA256 hashes still verify and are upgraded to Argon2id on the next successful login.
- Access tokens are signed with HS256 and expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutes by default).
- Configure a long, random `SECRET_KEY` in the hosting provider before deployment. Never commit real secrets to GitHub.
- Registration currently creates one organization per new user and makes that user its owner.
- Email verification, refresh tokens, invitations, role-based authorization for business APIs, and production security review are not implemented yet.
- Organization endpoints (see `organizations-api.md`) enforce membership and roles on the backend. Every future business endpoint must use the same dependencies.
- Login rate limiting is in-memory (per server process); see `known-issues.md`.

## Update account

`PATCH /api/v1/auth/me` with `{"full_name": "New Name"}` updates the display name of the signed-in user. Email changes require verification and are not supported yet.


## Social sign-in endpoints (added 2026-11-04)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/providers` | `{ "google": bool, "whatsapp": bool }` — which options are configured |
| GET | `/auth/google` , `/auth/google/callback` | Google OpenID Connect (see `google-sign-in.md`) |
| POST | `/auth/whatsapp/request-code` | Send a one-time code to a WhatsApp number (`202`) |
| POST | `/auth/whatsapp/verify` | Check the code, sign in or create the account (`AuthResponse`) |

`UserResponse` now has `email: string | null` (null for WhatsApp accounts) and `has_password: bool` (false for Google/WhatsApp accounts). `POST /auth/change-password` returns `400` for accounts without a password. See `whatsapp-sign-in.md`.
