# Background Job Progress and Live Frontend Feedback

**Status:** Cross-cutting architecture requirement captured for future implementation.  
**First intended use:** Product 02 lead-generation pipeline.  
**Existing reference:** Brand Intelligence already has durable sync jobs and a frontend status dashboard; reuse its proven patterns where appropriate rather than creating a competing job system.

## 1. Product requirement

Whenever the backend performs a long-running task, the customer-facing frontend should show what is happening, what has completed, what is currently running, what remains, and whether the task needs user action. Lead generation is the first major workflow that must use this pattern.

The backend remains authoritative. Progress must be persisted and recoverable; it must not exist only in browser state or in transient worker memory.

## 2. Pipeline stage display

For lead generation, show these stages in order:
1. Understanding the target and validating search criteria.
2. Discovering relevant businesses.
3. Extracting and enriching business contacts.
4. Cleaning, normalizing, and deduplicating records.
5. Checking email quality and verification evidence.
6. Qualifying and scoring leads.
7. Preparing results and outreach handoff.
8. AI outreach drafting (only when requested/enabled).
9. Quality, factuality, and compliance review.
10. Waiting for customer approval.
11. Sending approved email (only after all eligibility and approval gates pass).
12. Collecting delivery and campaign performance events.

A job may end after lead preparation if the customer did not request outreach. Sending and performance analysis are a separate campaign lifecycle and should not be falsely shown as completed during lead discovery.

## 3. Durable job and event model

Use a durable job record with tenant/organization ownership, creator, job type, input summary, overall status, current stage, timestamps, attempt count, safe error code/message, cancellation state, and result references. Store per-stage status, start/end times, counters, and retry metadata. Keep an append-only or otherwise replayable progress-event history with a monotonically increasing sequence number per job.

Suggested states:
- Job: `queued`, `running`, `waiting_for_input`, `waiting_for_approval`, `partially_completed`, `succeeded`, `failed`, `cancel_requested`, `cancelled`.
- Stage: `pending`, `running`, `succeeded`, `skipped`, `waiting`, `failed`, `retrying`, `cancelled`.

Record counters as structured values (for example businesses discovered, contacts extracted, duplicates removed, emails valid/invalid/risky/unknown, leads qualified, drafts generated, recipients eligible/suppressed, messages sent, bounces, and errors). Do not expose raw scraped content, secrets, stack traces, private provider payloads, or sensitive data in progress events.

Every organization-owned mutation must follow the existing activity-log rule. Enforce organization scope and role authorization for job reads, event streams, cancellation, retry, and result access.

## 4. Backend-to-frontend transport

Expose a tenant-authorized job snapshot endpoint and a progress-event endpoint. Prefer Server-Sent Events (SSE) for one-way worker-to-browser progress where supported, with event IDs/sequence numbers and reconnect replay. Provide bounded polling as a fallback and for clients/environments where SSE is unsuitable. Do not introduce WebSockets unless a real bidirectional interaction requirement justifies them.

The event stream is a delivery mechanism, not the source of truth. Persist events/state first; after reconnect the client must fetch a current snapshot and resume from the last sequence. If an event broker is used between workers and API processes, it must not replace durable database state. Avoid unbounded polling and stop subscriptions when jobs reach terminal states or the page unmounts.

## 5. Frontend experience

The job page should display:
- Overall status and a clear current-stage indicator.
- An ordered vertical stepper/timeline with completed, active, pending, skipped, waiting, and failed states.
- Short human-readable explanations of what each stage is doing.
- Stage-level counters and timestamps when meaningful.
- A progress bar only when a defensible percentage can be calculated; never invent precise percentages for indeterminate work.
- Partial results as they become safe and useful, with clear labelling that the job is still running.
- A clear distinction between no results, partial results, provider/source unavailable, blocked by source policy, and system failure.
- Retry, cancel, resume, or approval controls only when the backend says the action is allowed.
- Accessible status announcements (for example `aria-live`), keyboard navigation, and responsive mobile layout.

The UI must not imply that a stage is complete merely because a request was sent. It should render backend-confirmed states and explain when an update is delayed.

## 6. Reliability and safety

- Persist each meaningful state transition transactionally.
- Use idempotency keys and unique constraints to prevent duplicate jobs, lead inserts, campaign recipients, or email sends.
- Support worker restarts, lease expiry, stale-job detection, bounded retries, and explicit terminal failure.
- Separate retryable provider/network errors from permanent validation, authorization, and policy errors.
- Do not retry a stage if doing so could repeat an external side effect without idempotency or reconciliation.
- Cancellation is cooperative; report when a task is stopping and do not claim cancellation until workers confirm it.
- Enforce plan quotas, per-source rate limits, cost ceilings, and maximum job duration.
- Log internal diagnostics securely; expose only safe summaries to customers.

## 7. Testing requirements

Test state transitions, event ordering, sequence/replay after reconnect, polling fallback, tenant isolation, unauthorized access, worker crash/restart, stale jobs, retry idempotency, cancellation, partial results, skipped stages, source-policy blocks, provider outages, and frontend accessibility. Include integration tests with the actual persistence and event transport. A mocked worker test does not prove multi-process production delivery.

## 8. Implementation guidance

Reuse the existing durable Brand Intelligence sync-job concepts and frontend polling UI as a reference. First inspect whether the existing job model can be safely generalized; do not create a second generic job framework without a documented reason. Start with a small vertical slice: one durable job type, stage events, snapshot API, SSE or polling delivery, frontend stepper, and tests. Add further pipeline stages only as their backend work is implemented.
