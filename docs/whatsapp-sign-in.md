# WhatsApp sign-in

WhatsApp is **not** an OAuth/OpenID provider, so there is no "Log in with WhatsApp" redirect. AutoBizPro instead proves that a person controls a WhatsApp number: the API sends a 6-digit code to that number through the WhatsApp Business Platform (Cloud API), and the person types it back.

## Flow

1. `/whatsapp-login` asks for the number (with country code, e.g. `+2348012345678`).
2. `POST /api/v1/auth/whatsapp/request-code` `{ "phone": "+234…" }` → always `202` with the same message (it does not reveal whether the number has an account).
3. The person enters the code (and, for a new account, optionally their name).
4. `POST /api/v1/auth/whatsapp/verify` `{ "phone", "code", "full_name"? }` → the normal `AuthResponse` (token, user, workspace). A new number creates a user, a first workspace ("<name>'s Workspace" or "My Workspace") and an owner membership. An existing number signs in to the same account.

## Safeguards

- Codes are 6 digits, valid 10 minutes, single use; only the newest code works. Stored as an HMAC keyed with `SECRET_KEY` and bound to the phone number (a plain hash of 6 digits would be reversible).
- Max 5 wrong guesses per code (counted atomically before checking), 60-second resend cooldown and 5 codes per number per hour (all in the database, so they hold across workers), plus per-address limits (in memory, like the login limiter; move to Redis before multi-worker production).
- Accounts created this way have `email = null` and `has_password = false`. They cannot use password sign-in or password reset. There is no way yet to add an email or link a number to an existing account.

## Meta setup (external prerequisites)

1. A Meta developer app with the WhatsApp product and a WhatsApp Business Account + phone number.
2. A message template in the **Authentication** category with a **copy code** button, approved by Meta. The API sends the code as both the body parameter and the button parameter, as Meta requires.
3. A permanent system-user access token with `whatsapp_business_messaging`.
4. Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_OTP_TEMPLATE_NAME`, `WHATSAPP_TEMPLATE_LANGUAGE` (must match the approved template's language) and `WHATSAPP_GRAPH_API_VERSION` (check Meta's current supported version). Messaging is billed per conversation by Meta.

In development with nothing configured, the code is printed in the API server log so the flow can be tested; in production the endpoint answers `503` and the button is hidden.

**Not live-tested:** no request has been made to the real WhatsApp Cloud API; the sender is covered only by mocked tests.
