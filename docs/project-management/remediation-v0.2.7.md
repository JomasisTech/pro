# Stage One remediation report — BizPilotPro v0.2.7

**Baseline:** `bizpilotpro_v0_2_6_stage_one_remediated.zip`  
**Output:** `bizpilotpro_v0_2_7_stage_one_remediated.zip`  
**Audit date:** 2026-11-04  
**Scope:** Continue closing development gaps identified in the v0.2.6 audit. No browser/mobile QA or live provider verification is claimed.

## Executive summary

This pass closes two additional reliability gaps in the scheduled-publishing path:

1. Instagram long-lived access tokens nearing expiry are refreshed before the dispatcher uses them. The refreshed token is encrypted and persisted. Already-expired tokens are not sent through a refresh flow that cannot recover them; the job receives a reconnect-required error.
2. Facebook feed publishing and Instagram's final `media_publish` request no longer blindly retry after transport errors/timeouts or provider 5xx responses. Those outcomes may be ambiguous: the provider may have accepted the post even though the application did not receive a successful response. Such jobs are stopped with an explicit warning to verify the social account before creating a replacement.

This is a conservative duplicate-risk reduction, not complete provider idempotency or automated reconciliation.

## Changes made

| ID | Finding | Change | Status |
|---|---|---|---|
| R1 | Instagram long-lived tokens were not refreshed before expiry in the scheduled dispatcher | Added `get_instagram_access_token`; refreshes within seven days of expiry using Instagram Login's `ig_refresh_token` endpoint, encrypts the replacement, updates expiry, and commits it | Fixed for shared Instagram scheduler path; live provider behavior unverified |
| R2 | An expired Instagram token could only fail at dispatch time with no clear reconnect guidance | Expired token now stops with an explicit reconnect-required error; invalid refresh responses are normalized to a safe reconnect error | Fixed in code |
| R3 | Facebook/Instagram publishing network failures could be automatically retried even if the provider accepted the post | Ambiguous transport errors/timeouts and 5xx responses after the public publish request begins are marked failed and not automatically retried | Partially mitigated; manual provider-side reconciliation still required |
| R4 | Dispatcher comment said 15-minute lease while configured lease was 60 minutes | Corrected the stale comment | Documentation correction only; lease heartbeat remains open |
| R5 | New behavior lacked regression coverage | Added seven unit tests for refresh boundaries, persistence, expired tokens, provider guard, and ambiguous error classification | Fixed/tested |
| R6 | Release metadata was inconsistent with the new archive | Advanced backend, frontend and app version metadata to 0.2.7 | Fixed |

## Files changed

- `backend/app/integrations/instagram_tokens.py` (new)
- `backend/app/modules/posting/dispatcher.py`
- `backend/tests/test_instagram_token_refresh.py` (new)
- `backend/pyproject.toml`
- `backend/app/main.py`
- `frontend/package.json`
- `README.md`
- `docs/project-management/project-status.md`
- `docs/project-management/remediation-v0.2.7.md` (this report)

No database migration was required.

## Verification performed

| Check | Result |
|---|---|
| Backend automated tests | **186 passed, 2 skipped** |
| Python compileall (`app`, `tests`) | Passed |
| SQLite Alembic upgrade | Passed through `20261104_0021` |
| Alembic model/schema consistency | Passed — no new upgrade operations detected |
| Frontend package-lock generation | Not completed; registry access timed out and offline cache lacked `@tailwindcss/postcss` metadata |
| Frontend ESLint / production build | Not run; frontend dependencies are not installed |
| PostgreSQL application integration | Not run; no PostgreSQL server or psycopg driver available in this environment |
| Live Instagram token refresh | Not run; requires real provider credentials and network access |
| Live Facebook/Instagram publishing | Not run |
| Browser/mobile testing | Not performed, per code-only audit scope |

The backend suite used SQLite. SQLite results do not establish PostgreSQL compatibility. The attempt to install the missing PostgreSQL driver failed because this environment could not resolve the package registry; this is an environment limitation, not a test pass.

## Important behavior and limitations

- Instagram refresh is performed only for `provider == "instagram"`. Facebook Page tokens use a different lifecycle and are not incorrectly sent to Instagram's refresh endpoint.
- The Instagram refresh helper refreshes tokens with an expiry within seven days. Tokens that are already expired require reconnection.
- Facebook feed and Instagram `media_publish` ambiguous outcomes are marked `failed` with a warning. The user/operator must check the social account before manually scheduling a replacement. This avoids automatic duplicate retries but does not determine whether the provider actually published the post.
- Instagram media-container creation errors remain retryable because the final public `media_publish` operation has not yet begun.
- TikTok continues to use its provider publish ID and status-polling path. This pass does not change TikTok's state machine.
- The fixed 60-minute processing lease still has no heartbeat/renewal. A genuinely long-running job can outlive it; a lease token/heartbeat design remains outstanding.

## Still outstanding after this pass

1. **Frontend reproducibility and build:** generate and commit `package-lock.json`, install dependencies, run lint and production build.
2. **PostgreSQL integration:** run registration, tenant isolation, approved-draft scheduling, publishing state transitions and migrations against PostgreSQL 16.
3. **Scheduler lease heartbeat:** renew leases for long-running provider transfers and ensure a stale worker cannot renew a lease claimed by another worker.
4. **Complete provider reconciliation/idempotency:** add provider-aware recovery for uncertain outcomes, including durable operation identifiers and operator-facing reconciliation. Current fail-stop handling is only a safety mitigation.
5. **Distributed rate limiting:** replace process-local login and AI counters with shared atomic storage (e.g. PostgreSQL or Redis) before multi-worker deployment.
6. **Facebook token lifecycle:** document and implement the correct Page-token reauthorization/expiry strategy; do not assume Instagram's refresh endpoint applies.
7. **Hybrid Brand Intelligence:** social-post ingestion, latest-post synchronization, evidence/provenance, AI analysis and owner/admin conflict review remain unimplemented.
8. **YouTube recovery:** independent background processing polling and reliable browser-closure/resumable-upload recovery remain outstanding.
9. **Production and live-provider verification:** not established by this code-only pass.

## Release recommendation

**Do not treat v0.2.7 as production-ready.** The Instagram scheduled-token refresh and conservative ambiguous-publish fail-stop behavior are implemented and covered by unit tests, but PostgreSQL, frontend build, lease renewal, distributed rate limiting, full provider reconciliation and live provider verification remain open.

## Follow-up code increment — independent YouTube processing poller

After the v0.2.7 report, added `backend/app/modules/posting/youtube_worker.py`. It independently polls YouTube jobs with a verified video ID, refreshes/uses the connected account token through the existing account-token helper, and persists `uploaded`, `processing`, `published`, or `failed` status. This removes the requirement that a browser remain open for processing-status updates after upload completion.

Added four unit tests for provider-state mapping. Verification on the supplied archive: `DATABASE_URL=sqlite:///./test.db pytest -q` — **190 passed, 2 skipped**; `python -m compileall -q app tests` — passed. The two skipped tests include the environment-gated PostgreSQL integration check. This does not verify PostgreSQL, a scheduled/supervised worker deployment, or live YouTube API behavior. Browser-closure recovery for interrupted transfers remains open.
