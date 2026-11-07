# Plans, limits, and usage

## Change a limit in one place
Open `backend/app/core/plans.py` and edit the number in `PLAN_LIMITS`, for example:

```python
"free": {Metric.AI_CAPTIONS: 2, Metric.AI_VIDEO_SCRIPTS: 2, ...},
"standard": {Metric.AI_CAPTIONS: 10, Metric.AI_VIDEO_SCRIPTS: 10, ...},
"premium": {Metric.AI_CAPTIONS: 50, Metric.AI_VIDEO_SCRIPTS: 50, ...},
```
`None` means unlimited. Limits are per organization per calendar month (UTC). Enforcement, the usage endpoint, and error messages all read this one table, so a change reflects everywhere after the next deploy. The numbers currently in the file are **placeholders**.

## Add a new limited feature (for example, lead emails)
1. Add the name to `Metric` and a label to `METRIC_LABELS`; give it a number in **every** plan (a test fails if a plan is missing one).
2. Protect the endpoint with `Depends(require_quota(Metric.YOUR_METRIC))` instead of `get_membership`.
3. After the action succeeds, call `record_usage(db, organization_id, Metric.YOUR_METRIC)`.

`scheduled_posts` and `lead_emails` are declared but not enforced yet because those features do not exist.

## How it works
- `organizations.plan` stores each workspace's plan (`free` by default). Unknown values behave as `free`.
- `usage_events` stores one row per limited action; the month's total is compared with the plan limit.
- Over the limit returns **402** with a message saying which plan and limit applied.
- `GET /api/v1/organizations/{id}/usage` (any member) returns `plan`, `plan_name`, `period_start`, and per-metric `limit`, `used`, `remaining` (`null` = unlimited) for the UI.
- The separate hourly AI request cap (`AI_GENERATIONS_PER_HOUR`) is an abuse guard, not a plan feature.

## Billing later
There is deliberately **no endpoint that lets a user change their own plan**. When payments are added (Paystack first), the plan must be changed only by backend code that has verified the payment/webhook, mapping the provider's plan code to a key in `PLAN_NAMES`. If non-developers later need to edit limits without a deploy, move this table into the database behind an admin-only tool; the callers (`get_limit`) would not need to change.
