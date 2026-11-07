# Increment 31 — Owner profile controls, AI brand voice modes and admin recovery

**Date:** 2026-11-07  
**Baseline:** `autobizpro-dashboard-profile-polish-final.zip` (latest available project archive in this conversation).  
**Scope:** Product 01 / shared platform foundation only.

## What changed

### 1. Owner-controlled AI brand voice

- Added `business_profiles.brand_voice_mode`, defaulting existing and new profiles to `hybrid`.
- Added `business_profiles.custom_ai_instructions` (up to 2,000 characters).
- Added migration `20261107_0042_business_voice_controls.py`.
- Extended profile request/response schemas and frontend profile types.
- Added the brand voice mode selector and custom-instructions editor to the existing business onboarding/profile editor.
- Added the selected mode and instructions to the business-context read model.
- Caption and video-script prompts now include only the latest approved social-derived Brand Intelligence proposal when mode is `automatic` or `hybrid`.
- `manual` mode ignores social-derived voice analysis. Hybrid combines approved social observations with owner-defined tone/word preferences. Owner instructions remain separate and cannot override factual accuracy, safety or platform rules.
- Pending and rejected analyses are not used for content generation. Social observations do not overwrite the confirmed business profile.

### 2. Unified profile area entry points

- The `/profile` page now describes itself as the workspace's business and AI profile review area.
- Added clear navigation to Business Information, AI Brand Intelligence, Connected Social Accounts, Workspace & Team, Account Security, and Subscription & Billing.
- The profile summary displays the selected AI brand voice mode and custom instructions.
- Business editing continues to use the existing owner/admin-authorized `/onboarding` editor and existing version/confirmation flow; no parallel profile store was created.

### 3. Administrator-assisted password recovery

- Added `POST /api/v1/platform-admin/customers/{user_id}/password-recovery`.
- Requires platform-admin authorization, a support reason (20–500 characters), an active non-admin target, and an existing verified email.
- Invalidates prior unused reset tokens, creates a fresh hash-at-rest token with the configured expiry, and sends the link only to the customer's verified email.
- Customer chooses their own password via the normal reset page. Existing reset logic increments token version and invalidates sessions.
- Writes an append-only `customer.password_recovery_initiated` platform audit record.
- Added a recovery panel to the customer detail modal in `/platform`; the UI requires a reason and warns when email verification is absent.
- No password visibility, admin-set password, silent impersonation, or unverified email change was added.

## API and data contract

### Business profile additions

```json
{
  "brand_voice_mode": "hybrid",
  "custom_ai_instructions": "Use simple English and avoid slang."
}
```

`brand_voice_mode` accepts `automatic`, `manual`, or `hybrid`. The profile endpoint remains a full-replacement `PUT`; clients should send both new fields. Existing clients omitting `brand_voice_mode` receive the safe `hybrid` default, and omitted custom instructions clear to null under existing PUT semantics.

### Admin recovery request

```http
POST /api/v1/platform-admin/customers/{user_id}/password-recovery
Authorization: Bearer <platform-admin-token>
Content-Type: application/json
```

```json
{"reason":"Customer contacted support after losing access to their password."}
```

Returns HTTP 202 with a message explaining that a one-time link was sent to the verified address. It does not return the token.

## Verification performed

- `python -m compileall -q backend/app backend/tests backend/migrations/versions` — passed.
- Focused backend tests: `43 passed` across `test_profiles.py`, `test_content.py`, and `test_platform_admin.py`.
- The test runner environment lacked `pyotp` and `psycopg`; tests were executed with a temporary external `pyotp` import stub (no repository file added) and SQLite `DATABASE_URL`. The targeted tests do not exercise TOTP or real PostgreSQL behavior. This is not a full dependency-complete verification run.
- Fresh SQLite migration: `alembic upgrade head` — passed through `20261107_0042`.
- SQLite `alembic check` — reported `No new upgrade operations detected`.
- Frontend dependencies are not installed in this environment; ESLint, project TypeScript check, Next.js production build, Vitest and browser/mobile QA were not run.
- PostgreSQL 16, email delivery through production SMTP, and real admin recovery email delivery remain unverified.

## Remaining work / explicit boundaries

- Add optional personal phone-number management only with a proper verified-phone flow; do not treat an unverified number as account recovery evidence.
- Add a controlled support-case process for customers who have lost access to their verified email. Require independent identity verification and a second approval for changing the account email; do not create an admin bypass.
- A “Reset to AI suggestions” control is now present in the business profile editor. It switches to automatic mode and clears owner voice overrides/custom instructions after confirmation; the owner must still save the profile. A dedicated generated-sample preview remains future work.
- Add full personal account details editing if required; `/profile` now links to existing security and workspace settings but does not add phone editing.
- Run the full backend suite with all declared dependencies installed, plus PostgreSQL 16 integration tests.
- Run `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, and browser/mobile QA on a network-enabled Node 22 environment.
- Verify the admin reset email arrives through configured SMTP in staging and the normal reset link completes successfully.

## Handover instructions for the next AI/developer

1. Read root `AGENTS.md`, this increment report, `docs/project-management/HANDOVER.md`, `project-status.md`, `development-rules.md`, `known-issues.md`, `decisions-log.md`, and the profile/Brand Intelligence/platform-admin API docs.
2. Preserve the one-profile-per-workspace architecture. Do not create a second business-profile table or AI voice engine.
3. Preserve the rule that only approved Brand Intelligence proposals inform content generation.
4. Keep owner-confirmed facts authoritative. Any profile edit continues to create a version snapshot and clears `confirmed_at` for review.
5. Never expose password reset tokens in API responses or logs. Admin recovery must remain limited to an already-verified email and audited support reason.
6. Do not implement administrator impersonation or bypass verified-email ownership checks.
7. Complete the outstanding tests and front-end validation before marking this slice production-ready.
