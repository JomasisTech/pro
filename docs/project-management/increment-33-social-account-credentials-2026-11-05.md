# Increment 33 — add email/password to WhatsApp and Google accounts (2026-11-05)

## Added
- `POST /api/v1/auth/set-credentials` (authenticated). Body: `password` (8–128 chars) and `email` (required only when the account has none).
  - Refused with 400 if the account already has a password (use change-password), if an email is missing, or if a different email is sent for an account that already has one.
  - A taken email returns a generic 409 that does not reveal whose it is.
  - A newly added email starts unverified and a verification link is sent. If `EMAIL_VERIFICATION_REQUIRED=true`, the person must confirm the email before the account works again.
  - Like a password change, all other sessions end and a fresh token is returned. Throttled per user (reuses the verification limiter). Logs `auth.credentials_added`.
- Account security page: "Add an email and password" (WhatsApp) / "Add a password" (Google) form, replacing the "no password to change" note.

## Tests
`tests/test_set_credentials.py` (7). Not run (no dependencies in the authoring environment).

## Still open
Changing an existing email address; linking a phone number to an existing email account; password-change and sign-out-everywhere activity events.
