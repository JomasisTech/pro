# Stage One remediation report — BizPilotPro v0.2.6

**Baseline:** `bizpilotpro_v0_2_5_stage_one_remediated.zip`  
**Output:** `bizpilotpro_v0_2_6_stage_one_remediated.zip`  
**Audit date:** 2026-11-04  
**Scope:** Remaining development issues addressed in this remediation pass. No browser/mobile QA or live provider verification is claimed.

## Executive summary

This pass closes two important development gaps:

1. Scheduling now has an enforceable relationship to an approved, tenant-owned content draft. An administrator cannot use the scheduling endpoint to silently substitute different text for the approved copy.
2. Business-profile confirmation now creates an activity-log event in the same database transaction as the confirmation/version snapshot.

The frontend scheduling form was updated to select an approved draft and submit its exact content. A database migration preserves historical schedules by making the new draft reference nullable for existing records, while new API-created schedules require it.

## Changes made

| ID | Finding | Change | Status |
|---|---|---|---|
| R1 | Schedule records were not linked to an approved draft | Added `scheduled_posts.draft_id`, foreign key to `content_drafts`, and index | Fixed |
| R2 | API could accept arbitrary text unrelated to approval | API requires an organization-owned draft with `status=approved` and exact content match | Fixed |
| R3 | Draft could be changed after scheduling | Draft update/status-change API rejects mutation when a schedule references it | Fixed |
| R4 | Linked draft could be deleted | Draft deletion API rejects deletion when schedule history references it; FK uses `ON DELETE RESTRICT` | Fixed |
| R5 | Frontend schedule page did not select approved content | Added approved-draft retrieval, selector, immutable content preview and `draft_id` submission for Facebook/TikTok | Implemented; build pending |
| R6 | Profile confirmation was absent from activity history | Added transactional `profile.confirmed` event | Fixed |

## Files changed

### Backend application
- `backend/app/models/scheduled_post.py`
- `backend/app/api/v1/scheduling.py`
- `backend/app/api/v1/drafts.py`
- `backend/app/api/v1/profiles.py`

### Database
- `backend/migrations/versions/20261104_0021_scheduled_post_approved_draft.py`

### Tests
- `backend/tests/test_scheduling.py`
- `backend/tests/test_profiles.py`

### Frontend
- `frontend/src/lib/social.ts`
- `frontend/src/app/schedule-post/page.tsx`

### Project metadata and documentation
- `backend/pyproject.toml`
- `backend/app/main.py`
- `frontend/package.json`
- `README.md`
- `docs/project-management/project-status.md`

## Verification performed

| Check | Result |
|---|---|
| Backend automated tests | **179 passed, 2 skipped** |
| Python compileall (`app`, `tests`) | Passed |
| SQLite Alembic upgrade | Passed through `20261104_0021` |
| Alembic model/schema consistency | Passed — no new upgrade operations detected |
| Frontend production build | Not run — dependencies are not installed in this environment |
| Frontend ESLint | Not run — dependencies are not installed |
| PostgreSQL integration | Not run — no PostgreSQL service available |
| Browser/mobile testing | Not performed, per the code-only audit scope |
| Live social-provider testing | Not performed |

The backend test run used the repository's SQLite test fixture. The migration verification used a separate SQLite database. Neither result proves PostgreSQL compatibility.

## Important behavior and compatibility notes

- Existing scheduled-post rows retain `draft_id = NULL`; this avoids breaking historical data during upgrade.
- New schedule creation through the API requires `draft_id`. Direct database-created legacy/test rows can still have a null draft reference.
- The scheduled copy must exactly match the approved draft text.
- A draft that has any schedule history is immutable through the draft update endpoint. Its deletion is blocked so historical schedule provenance is retained.
- If a schedule is cancelled, the draft remains linked to that historical schedule and cannot be edited or deleted. This is intentionally conservative to preserve the exact approval record. A future product enhancement could introduce explicit draft versioning or a “duplicate as new draft” workflow.
- The scheduling page currently supports Facebook and TikTok. This pass does not add Instagram scheduling UI.

## Still outstanding after this pass

These are not claimed as fixed:

1. **Frontend dependency lockfile and build:** no `package-lock.json`; install, lint and production build remain outstanding.
2. **PostgreSQL application integration:** migrations and key workflows must be exercised against PostgreSQL 16, not just SQLite.
3. **Scheduler lease renewal:** the worker uses a fixed processing lease; a long-running upload can outlive it. A lease heartbeat/renewal mechanism remains outstanding.
4. **Provider idempotency and ambiguous timeout recovery:** an external provider may accept a post while the application fails before persisting confirmation. Safe reconciliation/idempotency remains outstanding.
5. **Distributed rate limiting:** login and AI throttles remain process-local.
6. **Credential lifecycle parity:** Facebook/Instagram refresh and expiry handling need further review and tests.
7. **Hybrid Brand Intelligence:** social-post ingestion, latest-post sync, evidence/provenance, AI analysis and owner/admin conflict review remain unimplemented.
8. **YouTube background recovery/status monitoring:** browser-closure recovery and independent processing polling remain outstanding.
9. **Production deployment and live provider verification:** not established by this code-only remediation.

## Release recommendation

**Do not treat v0.2.6 as production-ready.** The approved-draft scheduling enforcement and profile activity logging are implemented and backend-tested, but frontend compilation, PostgreSQL integration, scheduler reliability, distributed rate limiting and provider lifecycle work remain open.
