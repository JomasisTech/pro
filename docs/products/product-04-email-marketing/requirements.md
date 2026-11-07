# Product 04 — Email Marketing and AI Outreach Requirements

**Status:** Requirements captured for future product development; not implemented as a complete outreach product.  
**Related products:** Product 02 — Lead Management; Product 06 — Data Collection.  
**Current delivery scope:** Product 01 and foundation hardening remain active.

## Objective

Allow customers to prepare, review, approve, schedule, and send relevant business email campaigns, including personalised outreach to eligible leads generated or imported through Product 02.

## AI outreach preparation

For each selected lead, AI may draft a personalised message using customer-approved business details, the customer's offer, and verified/provenance-backed public business facts. The model must not invent a recent event, business problem, relationship, metric, or personal detail. If there is insufficient evidence, generate a neutral message or ask for more context.

The system should support subject, body, preview text, call to action, tone, language, and optional follow-up sequence drafts. Use structured output schemas, reusable templates, version history, and customer editing. Do not require a separate AI model for drafting and review; use specialised prompts and deterministic checks with the configured provider, and add an independent model only when evaluation demonstrates a meaningful quality improvement.

## Quality review

Before a draft is approved, check:
- Required fields and rendering validity.
- Factual claims against the supplied source evidence.
- Personalisation relevance and avoidance of fabricated details.
- Grammar, clarity, tone, spelling, and broken placeholders.
- Subject/body consistency and clear sender identity.
- Links, tracking settings, and unsubscribe footer.
- Policy, suppression, consent/lawful-basis, and recipient eligibility.

AI review is advisory, not a guarantee that a message is accurate, legally compliant, or human-written. The customer remains responsible for approving campaign content. Store review findings and draft versions for audit.

## Approval and delivery safeguards

- Default to customer review/approval before the first send and before enabling any automation.
- Never send to suppressed, unsubscribed, bounced, invalid, or otherwise ineligible recipients.
- Publicly listed email addresses do not automatically establish permission for marketing. Enforce a documented lawful-basis/consent policy by jurisdiction and campaign type, with legal review before launch.
- Include sender identity and functional unsubscribe handling where required; propagate opt-outs to a durable suppression list promptly.
- Enforce sending limits, domain/provider reputation safeguards, bounce/complaint thresholds, and abuse monitoring.
- Use idempotent campaign and recipient delivery records to avoid duplicate sends on worker retries.
- Provide pause/cancel controls and safe recovery for interrupted campaigns.
- Use a configured email provider; track provider message IDs and delivery/bounce/complaint events where supported.

## Customer interface

Provide campaign setup, recipient eligibility preview, AI draft editor, review checklist, approval queue, scheduling, pause/cancel, delivery status, bounce/complaint/unsubscribe metrics, and campaign analytics. Link each recipient to its lead/contact record and source provenance where permitted.

## Acceptance criteria

Campaigns cannot be sent without passing server-side eligibility and suppression checks. AI-generated drafts are editable and versioned. Approval is attributable to a user and timestamp. Retries cannot duplicate delivery. Unsubscribe and suppression events are durable and take precedence over queued sends. Live provider tests and jurisdiction-specific compliance review are required before production activation.
