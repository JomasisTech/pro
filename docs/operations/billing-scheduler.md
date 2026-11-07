# Billing scheduler operations

## Managed scheduler

The Render blueprint defines one cron service, `bizpilotpro-billing-maintenance`, scheduled every five minutes. Render documents cron scheduling and its single-run guarantee in its [Cron Jobs guide](https://render.com/docs/cronjobs); the service configuration uses the [Blueprint YAML specification](https://render.com/docs/blueprint-spec). It runs:

```bash
python -m app.jobs.run_billing_maintenance
```

The runner uses bounded batches and executes in this order:

1. Queue one-time recurring-billing activation notices and due renewal reminders; deliver the email outbox.
2. Reconcile existing uncertain Paystack renewal references (verification only).
3. Process a Paystack-directed retry only when Paystack supplied an explicit retry window; at most one retry is permitted for that billing period.
4. Process new due renewals only when `BILLING_RENEWALS_ENABLED=true`.
5. Process cancellation, grace-period and expiry lifecycle transitions.

The runner emits one JSON summary line with start/end timestamps, feature flags and bounded task counts. An infrastructure exception emits `status=error` and exits non-zero so the hosting scheduler can mark the run failed. It deliberately excludes exception text and credentials from structured output.

## Required deployment configuration

Set these on the cron service, using the same production database and security configuration as the API:

- `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`, `CORS_ORIGINS`, `MEDIA_PUBLIC_BASE_URL`, `FRONTEND_BASE_URL`.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_STARTTLS`, `EMAIL_FROM`.
- `PAYSTACK_SECRET_KEY` and `BILLING_AUTHORIZATION_ENCRYPTION_KEY` only when preparing for recurring-charge test mode.
- Keep `BILLING_RENEWAL_NOTIFICATIONS_ENABLED=false` until real SMTP delivery is tested.
- Keep `BILLING_RENEWALS_ENABLED=false` until live Paystack test-mode and PostgreSQL concurrency verification are complete.

The Render cron service is intentionally provisioned with both billing flags set to false. The service can supervise safe reconciliation/lifecycle operations without initiating a new charge.

## Monitoring and supervision

1. In the Render dashboard, open the cron service and review **Events** and **Logs**. Confirm one successful run every five minutes.
2. Configure workspace/service failure notifications in Render. Alert on a failed cron run, repeated restarts, or a missing successful run for more than 15 minutes.
3. Inspect JSON fields `renewal_reconciliation`, `provider_directed_retries`, `due_renewals`, `email_delivery`, and `subscription_lifecycle`. Alert on persistent `needs_attention`, `provider_unavailable`, `failed`, or SMTP `retrying`/`failed` counts rather than treating a successful process exit as proof that every payment succeeded.
4. Keep a single managed scheduler service for this task. Do not also run the same commands from a second cron provider until a distributed scheduler lock is added and concurrency-tested on PostgreSQL.
5. Monitor the API and cron service against the same database migration head. Apply Alembic migrations before deploying the scheduler version that expects them.
6. Keep a human review path for `verification_pending`, `needs_action`, and provider retry exhaustion. Do not manually re-run a charge for an ambiguous reference.

## SMTP smoke test

After configuring the SMTP environment variables, run from `backend/`:

```bash
python -m app.jobs.check_billing_readiness --email-to your-controlled-test-inbox@example.com
```

This command checks database connectivity and sends one explicit test message to the supplied inbox. It never sends a message unless `--email-to` is provided. Do not use a customer address. A successful SMTP handoff still needs inbox/spam-folder confirmation.

## Provider-directed retry policy

Paystack's recurring-charge documentation describes the card-regulator response `Charge attempt cannot be fulfilled until X minutes` and its `retry_by` field. BizPilotPro only schedules a retry when the Paystack adapter receives that explicit regulator response and can extract a valid retry window no more than 24 hours ahead. It waits until the provider-specified time, preserves the rejected reference in the renewal-attempt audit record, and generates a fresh unique reference for the retry. Paystack documents unique references per transaction; a second retry is not allowed.

Generic declines (for example insufficient funds), customer OTP/3DS challenges, network timeouts, unrecognized statuses and verification mismatches are never automatically retried. Ambiguous outcomes go through verification-only reconciliation. The Paystack Transaction API requires unique references for transactions, so the retry receives a new reference only after the first request is explicitly rejected; the old reference remains in the attempt record. This is a conservative integration rule, not a claim that Paystack has separately approved BizPilotPro's merchant configuration. See [Paystack Charge Authorization](https://paystack.com/docs/api/transaction/) and [Transaction Errors](https://paystack.com/docs/api/errors/transaction/). Confirm behavior with Paystack test mode and the merchant account before enabling recurring charges.

## Manual recovery commands

```bash
python -m app.jobs.run_billing_maintenance
python -m app.jobs.reconcile_subscription_renewals
python -m app.jobs.process_billing_notifications
```

Do not run separate overlapping schedulers in production.
