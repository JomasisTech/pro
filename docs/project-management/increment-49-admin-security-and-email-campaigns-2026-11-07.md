# Increment 49 — administrator security monitoring and owner email campaigns

## Delivered

### Administrator security
- Successful password, Google and WhatsApp sign-ins continue to use the shared login telemetry helper; records now also retain the resolved client IP address.
- Password and TOTP failures for an identifiable registered account are recorded as failed sign-in events. Unknown email addresses are deliberately not linked to user records.
- Owner-only endpoints expose recent sign-in records and failed administrator sign-ins.
- Owner can revoke all tokens for a delegated administrator or configured owner by incrementing the target user's `token_version`. This invalidates every existing session for that account; the user must sign in again.
- Session visibility is based on recorded sign-in events, not a live per-device session registry. The token system remains account-wide, so revocation is account-wide.
- Existing append-only platform audit history records administrator role changes and security revocations. Campaign creation/completion is also audited.

### Email campaigns
- Owner-only `/platform-admin/email-campaigns` endpoints provide recipient count, campaign history and campaign creation.
- Recipient set is snapshotted when queued: registered accounts with a non-empty **verified** email address. Unverified addresses are excluded to reduce misdelivery and abuse.
- Dashboard includes subject/body editor, an explicit confirmation prompt, recipient count, campaign status and sent/failed totals.
- Sending requires configured SMTP (`SMTP_HOST`, `SMTP_PORT`, sender address and provider credentials as applicable). If SMTP is missing, API returns 503 rather than pretending to send.
- Campaigns are persisted with recipient-level pending/sent/failed status. FastAPI background task sends sequentially in groups of 25 and commits progress so the owner can inspect outcomes.
- Message body is plain text. Use this feature for service/platform announcements; marketing campaigns require appropriate consent, unsubscribe/suppression handling and jurisdiction-specific compliance before use.

## Database
Migration `20261107_0048` follows `20261107_0047` and:
- adds `ip_address` and `success` to `platform_login_events`;
- creates `platform_email_campaigns` and `platform_email_recipients`.

Deploy with:

```bash
alembic upgrade head
```

## Operational limitations and follow-up
- FastAPI `BackgroundTasks` is process-local, not a durable distributed queue. If a process exits during a campaign, a campaign may remain `sending`; production should move delivery to the existing durable worker/outbox infrastructure and add stale-job recovery.
- SMTP acceptance is not inbox delivery. Bounce, complaint and unsubscribe webhooks require a provider with event support; sent means SMTP accepted the message, not guaranteed inbox placement.
- Session records are login events, not individually addressable browser/device sessions. The current revocation control invalidates all sessions for one admin.
- Raw IP addresses are stored for administrator security review. Define and enforce a retention period before broad production rollout.
- A large list sends serially and can take time; a production queue should enforce rate limits and provider quotas. Campaign is owner-only and all recipients are snapshotted to avoid a changing audience during delivery.

## Verification
- `python -m compileall -q backend/app backend/migrations` passed.
- Full SQLite Alembic upgrade through `20261107_0048` passed using a fresh temporary database.
- Targeted pytest could not start because `pyotp` is not installed in this authoring environment. Frontend dependencies are absent, so TypeScript/lint/build/browser checks were not run.
- No real SMTP delivery or production deployment was performed. Configure SMTP and send a controlled test to owner-managed test accounts before sending a live all-user announcement.
