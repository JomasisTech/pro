# Screenshot follow-up implementation report — 2026-11-04

## Implemented in this increment

### Invitation management
- Added tenant-scoped `GET /api/v1/organizations/{organization_id}/invitations` for owners and admins.
- Added tenant-scoped `DELETE /api/v1/organizations/{organization_id}/invitations/{invitation_id}` for owners and admins. Only pending invitations can be revoked; accepted records remain as history.
- Invitation revocation writes an organization activity-log event before commit.
- Extended Workspace Settings with invitation creation, role selection, pending/history display, and revoke controls. Admins can invite members; owners can invite admins.

### Distributed rate limiting
- Added `RedisFailedAttemptLimiter` using Redis atomic increments and expiry, with namespaced hashed keys.
- `REDIS_URL` selects the shared implementation for login account/IP protection, password reset/change, WhatsApp request/verification, and AI caption/video generation.
- Without `REDIS_URL`, the existing bounded in-memory limiter remains available for local development and tests. A configured Redis failure propagates rather than silently weakening production controls.

### Billing readiness
- Added `/api/v1/billing/plans` and `/api/v1/billing/readiness` using the central plan catalog.
- Added Paystack environment settings. The API explicitly reports placeholder prices and disabled checkout/webhooks; it does not create fake subscriptions or claim payment support is live.

## Still outstanding from the screenshot

1. **Email verification:** implemented in the 2026-11-04 continuation (migration `20261104_0026`): SHA-256 token digests, expiring single-use links, SMTP delivery, generic/rate-limited resend, frontend confirmation/resend page, and configurable login enforcement. Live SMTP delivery and production rollout still require staging validation.
2. **Hybrid Brand Intelligence:** requires official provider-specific post retrieval, latest-20 synchronization, source/provenance and confidence records, analysis, conflict detection against user-confirmed profile facts, and an owner/admin review UI. No social provider is assumed to grant unsupported scopes.
3. **Full billing:** needs approved NGN pricing, subscription/customer persistence and migrations, Paystack initialization/verification, signed and idempotent webhook handling, lifecycle state transitions, and a frontend billing/plan management workflow.
4. **Database migrations:** none were added in this increment because existing invitation storage is already migrated, Redis state is external, and billing remains read-only. Migrations are required with the future verification-token, brand-evidence, and subscription tables.
5. **Frontend and integration verification:** install frontend dependencies, run lint/build, browser-test invitation workflows, and validate Redis/PostgreSQL/SMTP/payment/social-provider integrations in staging.

## Verification performed

- Python compileall: passed.
- Focused backend tests: **30 passed** (`test_organizations.py`, `test_billing_readiness.py`, `test_rate_limit.py`) on SQLite.
- Full backend suite: attempted; execution exceeded the available 120-second window. No full-suite pass is claimed.
- Frontend lint/build, PostgreSQL migrations, live Redis, SMTP, Paystack, and social-provider calls: not run.


## Continuation — email verification

- Added `email_verification_tokens` with hashed secrets, expiry, single-use consumption, and cascading user cleanup.
- Registration issues a verification link; resend responses do not disclose whether an account exists and requests are rate-limited by email and client IP.
- Added public `POST /auth/verify-email` and `POST /auth/resend-verification`.
- Added `/verify-email` frontend route; verification secrets travel in URL fragments and are removed from browser history before submission.
- Added `EMAIL_VERIFICATION_REQUIRED` (default false for backwards compatibility) and token TTL / resend rate settings. Google-verified email remains trusted; WhatsApp accounts without an email are unaffected.
- Added backend regression tests for registration delivery, hashed token persistence, successful verification, replay rejection, and non-enumerating resend.
