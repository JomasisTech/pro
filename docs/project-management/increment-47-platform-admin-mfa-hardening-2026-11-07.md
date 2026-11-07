# Increment 47 — Platform administrator MFA enforcement

Date: 2026-11-07

## Delivered

- Platform administrator access now requires an enabled authenticator-based TOTP factor in addition to the existing verified-email allowlist.
- Password sign-in accepts an optional `totp_code`. When a configured platform administrator has enrolled TOTP, a valid current code is mandatory before an access token is issued.
- Invalid or missing administrator TOTP codes count against the existing password-login attempt limiter (account and optional IP limiter).
- Enabling TOTP increments `token_version`, invalidating all existing sessions. The administrator must sign in again with password plus authenticator code.
- OAuth/WhatsApp sign-in does not bypass MFA for an enrolled platform administrator; such an administrator is directed to the password-plus-TOTP sign-in flow.
- The login screen now exposes an optional authenticator-code field. Regular customers may leave it blank.
- All routes using `require_platform_admin` are protected by the MFA enrollment requirement.

## Enrollment / rollout

1. Keep the intended owner address in `PLATFORM_ADMIN_EMAILS` and ensure that email is verified.
2. Sign in normally before enrollment; the admin APIs remain blocked until MFA is enabled.
3. Open Profile → Account security (`/security`) and set up an authenticator app.
4. Verify the first code. Existing sessions are invalidated at this point.
5. Sign in again with email, password and the authenticator code. Then open `/platform`.
6. Store authenticator recovery arrangements securely. There is no administrator MFA bypass or secret-reset endpoint in this increment.

## Security notes

- TOTP secret remains stored in the existing user TOTP fields; this increment does not introduce a new migration.
- TOTP is not required for ordinary customer accounts.
- An enrolled platform administrator must use password sign-in; provider sign-in is intentionally blocked to avoid an MFA bypass.
- The current platform-admin identity model remains a verified-email environment allowlist. Granular delegated roles, role assignment workflows, recovery codes, MFA reset with dual control, and security-event alerting are not yet implemented.
- No TOTP values or secrets are written to login telemetry.

## Validation

- Python source compilation is required before packaging.
- Frontend production build and full automated tests must be run in a dependency-complete CI environment; this working environment may not contain all project dependencies.
