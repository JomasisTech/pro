# Increment 28 — Lead Generation and Live Pipeline Progress Requirements

**Date:** 2026-11-05  
**Type:** Documentation and product-requirements capture only  
**Baseline:** Increment 27  
**Application code changed:** No  
**Database migrations added:** No  
**Provider integrations added:** No

## Owner-approved direction

The owner described an AI-assisted workflow where a customer specifies an industry and target requirements, the platform discovers relevant businesses, extracts publicly available business contacts, cleans and checks contact data, qualifies and scores leads, prepares personalised outreach, reviews quality/compliance, and—after customer approval and eligibility checks—sends email and measures campaign performance.

The owner also requires the frontend to show each backend processing stage while it runs, rather than leaving customers waiting without feedback.

## Documentation added

- `docs/products/product-02-lead-management/requirements.md`
- `docs/products/product-04-email-marketing/requirements.md`
- `docs/products/product-06-data-collection/requirements.md`
- `docs/architecture/background-job-progress.md`

Project instructions and handover records updated:
- `AGENTS.md`
- `docs/project-management/development-rules.md`
- `docs/project-management/master-development-prompt.md`
- `docs/project-management/project-status.md`
- `docs/project-management/completed-work.md`
- `docs/project-management/decisions-log.md`
- `docs/project-management/HANDOVER.md`

## Key decisions recorded

1. Use one AI provider with separate structured tasks where useful; do not require a separate AI model for every stage. Use deterministic code for validation, deduplication, access control, quotas, suppression, idempotency, and sending.
2. Treat discovery, extraction, cleaning, scoring, outreach drafting, quality review, approval, sending, and analytics as logically separate stages with observable state.
3. Persist job/stage state and progress events. The frontend displays backend-confirmed progress, counters, partial results, waiting states, and safe errors. Progress survives page navigation and reconnects.
4. Prefer replayable Server-Sent Events (SSE), with an authorized job snapshot and bounded polling fallback. Do not add WebSockets without a real bidirectional need.
5. Inspect and reuse the existing Brand Intelligence durable sync-job implementation before creating another job framework.
6. Use approved/licensed sources, preserve provenance, respect terms and access controls, and do not fabricate or guess email addresses.
7. Publicly visible business contact information is not blanket permission to send marketing. Product 04 must enforce the applicable lawful-basis/consent policy, suppression, unsubscribe, customer approval, and sending safeguards.

## Verification

- Checked all newly created documentation files are present.
- Checked referenced relative documentation paths exist.
- Confirmed this increment makes no application-code or schema changes; application tests are therefore not applicable to this documentation-only increment.
- ZIP integrity is checked during packaging.

## Scope boundary

These requirements are recorded for future Product 02, Product 04, Product 06, and cross-cutting progress UX. They do not change the current delivery scope. Foundation hardening and Product 01 remain active; do not implement future products until project status and the owner explicitly authorize that transition.

## Next development work

Continue the previously planned foundation verification: PostgreSQL 16 integration checks, then complete frontend dependency installation/lockfile, lint, TypeScript, build, and browser verification in a network-enabled environment. Product 02 implementation should be scheduled only after Product 01 and foundation readiness are established.
