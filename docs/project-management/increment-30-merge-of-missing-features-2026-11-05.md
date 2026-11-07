# Increment 30 — features ported from the parallel build (2026-11-05)

Baseline: the Increment 29 repository. A separate build of the Stage 1 items was compared against it; almost everything there already existed here in a more complete form (email verification, Redis rate limiting, invitation list/revoke, Brand Intelligence sync, billing). Only the gaps below were ported. Nothing was removed or restructured.

## Added
1. **Invitation resend** — `POST /organizations/{id}/invitations/{invitation_id}/resend` (owner/admin). Issues a new token (the old link stops working), extends expiry 7 days, 60-second cooldown (`INVITATION_RESEND_COOLDOWN_SECONDS`, HTTP 429 + `Retry-After`), refuses accepted invitations, writes an `organization.invitation_resent` activity entry. New column `organization_invitations.last_sent_at` (migration `20261105_0040`).
2. **Invitation status** — the admin list now returns `status` (`pending`/`accepted`/`expired`) and `last_sent_at`.
3. **Admin guard** — admins can no longer revoke an admin-role invitation (owners only), matching the existing rule for creating them.
4. **Accepting an invitation verifies the email address** (the link was delivered to that address).
5. **Rule-based brand analysis** — `POST /brand-intelligence/analyze?method=rules` builds a proposal from the same stored observations with no AI key and no model call (`app/modules/brand_intelligence/heuristics.py`). It returns the same keys as the AI proposal plus `evidence_level` (initial/developing/well_supported, from post count, recency and duplicates), `suggestions` and `metrics`; it leaves `proposed_voice` empty and reports profile differences (frequent theme missing from the profile, listed products never mentioned, avoided words used) as `conflicts`. It goes through the existing pending → approve/reject review. The default (`method=ai`) behaviour is unchanged, including 503 without a provider.
6. **Frontend**: Resend button and status/expiry text in the workspace invitation list; `lib/invitation-helpers.ts`; first Vitest suite (`npm test`, `vitest.config.ts`) and a CI step.

## Tests added
- `tests/test_organizations.py`: 4 invitation tests (status, resend/cooldown/expiry/old-link, accept verifies email, admin/member guards).
- `tests/test_brand_intelligence.py`: 3 rule-based analysis API tests.
- `tests/test_brand_rules.py`: 12 pure-logic tests.
- `frontend/src/lib/__tests__/invitation-helpers.test.ts`: 4 tests.

## Verification actually performed
The environment had no FastAPI/SQLAlchemy/pytest and no network. Run: `compileall` (pass); undefined-name scan (clean); the 12 pure tests in `test_brand_rules.py` (**12 passed**, several hash seeds); the 4 frontend helper tests via `tsc` + Node shim (**4 passed**). **Not run:** the 7 new API tests, the full existing suite (regression), migration `0040` (`alembic upgrade head`, `alembic check`), `npm install`/lint/typecheck/build/Vitest, and the workspace page in a browser.

## Not ported (already covered or out of scope)
Email verification, Redis limiter, billing, provider post sync (all present and more complete here); a manual "paste posts" analysis screen (here, observations come from provider sync or the manual-observation endpoint).
