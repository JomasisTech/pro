# Increment 48 — Platform administrator roles

## Purpose
Reduce the blast radius of delegated administrative accounts. The environment-configured `PLATFORM_ADMIN_EMAILS` accounts remain owner-level super administrators; all other platform administrators must have a database assignment.

## Roles and permissions

| Role | Permissions |
|---|---|
| `support` | `customers.read`, `customers.support`, `activity.read`, `login_events.read` |
| `finance` | `finance.read`, `finance.manage`, `customers.read` |
| `operations` | `operations.read`, `operations.manage`, `customers.read`, `activity.read`, `login_events.read` |
| `viewer` | `overview.read`, `customers.read`, `activity.read`, `login_events.read` |

Support actions include customer password recovery initiation (verified-email reset only) and customer suspend/reactivate. Finance management includes adding verified operating-cost ledger entries. Operations management includes retrying eligible webhooks and running bounded reconciliation. Billing price administration remains restricted to configured owners.

## API
- `GET /api/v1/platform-admin/admins`: owner-only delegated role directory.
- `POST /api/v1/platform-admin/admins`: owner-only role grant/update; payload `{email, role}`.
- `DELETE /api/v1/platform-admin/admins/{user_id}`: owner-only revocation.
- Existing platform-admin endpoints now use permission-specific dependencies.

Assignments require a registered, active, verified-email account. Grants and revocations are recorded in `platform_admin_audits`. Owner accounts are determined from the verified email allowlist and cannot be demoted by the delegated role API.

## MFA and login
Delegated administrators must enroll authenticator MFA. Password login requires a valid TOTP code. Google and WhatsApp login cannot issue an administrator session. Every protected API independently checks the MFA enrollment and required permission. Revoking the database assignment takes effect on the next API request (the token is not itself a role grant).

## Migration and deployment
Run Alembic migration `20261107_0047` (parent `20261107_0046`). No manual SQL changes are needed. The owner should grant roles only to trusted verified accounts and confirm that each delegate has enrolled MFA before operational use.

## Validation and remaining work
Python syntax compilation and migration upgrade are the minimum validation gates. Full backend integration tests, frontend TypeScript/build, browser permission-matrix tests, and deployment smoke tests must be completed in CI. Future work: optional per-action approvals for high-risk financial operations, time-bounded grants, admin session/device management, and alerting on role changes.
