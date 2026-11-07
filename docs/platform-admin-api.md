# Platform administration API

All endpoints under `/api/v1/platform-admin` require a verified platform-owner email listed in `PLATFORM_ADMIN_EMAILS`. Frontend visibility is not an authorization boundary; each endpoint enforces the server-side dependency.

## Top customer spending leaderboard

`GET /api/v1/platform-admin/top-customers`

Query parameters:
- `currency`: `NGN` (default) or `USD`.
- `sort`: `desc` (default, highest spend first) or `asc` (lowest spend first).
- `limit`: integer 1–10 (default 10).

The endpoint groups successful payment transactions (`status=paid`) by `initiated_by_user_id` and sums `amount_minor`. It excludes pending/failed payments and transactions without an attributable user. Each result includes `rank`, `user_id`, `full_name`, `email`, `is_active`, `total_spend_minor`, `currency`, `successful_payment_count`, and `last_payment_at`.

NGN and USD are deliberately ranked separately. The system does not add amounts in unlike currencies or invent an exchange rate. The ranking represents gross successful payment volume, not net revenue: refunds and chargebacks are not yet supported. Attribution is to the user who initiated checkout, not every member of the paying organization.

Example response shape:

```json
{
  "items": [
    {
      "rank": 1,
      "user_id": "<uuid>",
      "full_name": "Customer name",
      "email": "customer@example.com",
      "is_active": true,
      "total_spend_minor": 1500000,
      "currency": "NGN",
      "successful_payment_count": 3,
      "last_payment_at": "2026-11-04T12:00:00Z"
    }
  ],
  "currency": "NGN",
  "sort": "desc",
  "limit": 10,
  "metric": "lifetime_successful_payment_spend",
  "note": "Ranked by successful payments initiated by each customer; currencies are ranked separately."
}
```

## Administrator-assisted password recovery (Increment 31)

`POST /api/v1/platform-admin/customers/{user_id}/password-recovery`

Requires the verified platform-owner allowlist and JSON body `{"reason":"..."}` (20–500 characters). The target must be an active non-admin customer with an existing verified email address. The API invalidates any older unused password-reset tokens, creates a fresh one-time token using the same hash-at-rest and expiry rules as self-service password recovery, and sends the link only to the customer's already-verified email. The customer chooses their own new password through the normal reset page; the administrator never sees or sets it. The reset flow increments `token_version`, invalidating existing sessions.

Every initiation is recorded in `platform_admin_audits` as `customer.password_recovery_initiated`, including the administrator, target and support reason. The endpoint refuses accounts without a verified email, suspended accounts, and platform administrators. If a customer has lost access to their verified email, this endpoint deliberately does not bypass identity verification; a separate documented/manual support process is still required before changing account email ownership.
