# Increment 45 — Provider-reported AI token metering

Date: 2026-11-07

## Purpose
Record real token counts returned by the AI provider so platform operators can understand usage and later reconcile actual provider invoices. This is separate from plan quota counters, which count feature actions rather than tokens.

## Implementation
- `AIUsageRecord` stores organization, optional user, provider, model, feature, prompt tokens, completion tokens, total tokens, optional estimated USD micros, and creation time.
- Migration `20261107_0045_ai_usage_records.py` creates the table and reporting index. Parent migration is `20261107_0044`.
- `GeneratedText` now carries optional provider usage fields. The OpenAI Chat Completions adapter reads the provider's `usage` object and validates non-negative integer counts.
- `record_ai_usage` persists only provider-returned usage. It never estimates tokens from prompt/output character length.
- Metered features: caption generation, video-script generation, and AI brand analysis. Rule-based brand analysis does not call a provider and is not metered as AI usage.
- `/api/v1/platform-admin/financials` includes grouped AI token usage; `/api/v1/platform-admin/ai-usage` provides a dedicated admin report.
- Platform admin financial panel displays provider/model/feature and prompt/completion/total tokens.

## Pricing and accounting safeguards
- Set `OPENAI_INPUT_USD_PER_MILLION_TOKENS` and `OPENAI_OUTPUT_USD_PER_MILLION_TOKENS` for the exact configured model to enable estimates.
- Both rates default to zero. If rates are not explicitly configured, `estimated_cost_usd_micros` is null. This prevents invented or stale prices from being treated as expenses.
- Estimates are USD only and are not a substitute for provider invoices. Discounts, cached input pricing, batch pricing, tool charges, taxes, and provider adjustments are not represented by this simple rate model.
- Do not add AI estimates to manual cost ledger totals as though they were invoices; avoid double counting when reconciling provider invoices.
- Older calls have no historical token data and are not backfilled.
- If provider usage is omitted, the successful AI result still returns normally; the metering helper skips the record rather than fabricating usage.

## Operational steps
1. Back up the production database.
2. Deploy code and run `alembic upgrade head`.
3. Configure the two rate variables only after verifying current pricing for the exact model in use. Leave them unset/zero to collect tokens without cost estimates.
4. Verify an AI generation and inspect `/platform` financial monitoring or `/api/v1/platform-admin/ai-usage` as a platform admin.
5. Reconcile estimated amounts against provider billing exports before financial reporting.

## Remaining work
- Add provider invoice import/reconciliation and model-specific pricing schedules with effective dates.
- Extend metering to any future AI provider adapters and any AI call sites added outside the three instrumented flows.
- Consider recording provider request IDs for invoice-level reconciliation if the provider returns them and retention policy permits.
- Add tests with mocked provider usage and missing/malformed usage responses.
