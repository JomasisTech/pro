# Increment 46 — Refund and chargeback reconciliation

Date: 2026-11-07

## Delivered

- Added `PaymentAdjustment` ledger and Alembic migration `20261107_0046` (parent `20261107_0045`).
- The Paystack webhook endpoint now handles signed `charge.refund`, `dispute.create`, and `dispute.resolve` events in addition to the existing successful-charge flow.
- Adjustment records link to the original server-created payment transaction, retain provider identifiers, type, state, amount, currency, short reason and timestamps, and use the webhook event key for idempotency.
- Raw webhook payloads, card details, bank details and customer secrets are not stored.
- Added platform-admin reporting at `GET /platform-admin/payment-adjustments` and grouped refund/dispute totals in `GET /platform-admin/financials`.
- Admin financial UI displays refunds, open chargeback exposure and chargeback outcomes separately.

## Safety and accounting rules

- Only provider-signed webhooks enter this path. The webhook signature is checked before any event is processed.
- Adjustments are linked to an existing Paystack payment by its original reference; unmatched events are not guessed or attached to another customer.
- Currency must match the original payment. Provider amounts are expected in minor units.
- Refunds are recorded as processed adjustments. New disputes are recorded as pending exposure. A dispute-resolution event updates the matching dispute only when a provider adjustment ID is available.
- The app deliberately does not publish a net-profit or final net-revenue figure. Refunds and chargebacks can overlap, provider fees/reversals require reconciliation, and the manual cost ledger is not a complete expense base. The admin UI warns against double-counting a refund and dispute tied to the same amount.
- No refund initiation or dispute submission endpoint was added. This increment records provider outcomes; it does not move money or make decisions on behalf of the platform owner.

## Known limitations / follow-up

- Confirm the exact Paystack dispute-resolution payload fields against live/sandbox webhook examples before relying on resolution state for accounting. If a resolution event does not carry the same dispute ID, its record remains pending and requires manual investigation.
- Add a reconciliation queue for unmatched or incomplete adjustment events, with administrator review and audit trail.
- Add provider API backfill/reconciliation for missed webhooks, pagination, fees and reversal events.
- Add customer-facing refund status only after product policy and provider behavior are defined.
- Automated tests for duplicate webhooks, partial/multiple refunds, dispute create/resolve, mismatched currency, missing references and overlapping refund/dispute amounts remain required.

## Validation

- `python -m compileall -q backend/app backend/migrations` passed.
- Full SQLite Alembic upgrade through `20261107_0046` passed.
- Full backend/frontend automated suites and live Paystack sandbox tests were not run in this environment.
