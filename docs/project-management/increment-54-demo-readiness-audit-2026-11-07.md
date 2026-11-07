# Increment 54 — Demo readiness audit and corrections

Date: 2026-11-07

## Audit scope

Reviewed the customer demo sign-in, platform-owner demo sign-in, backend demo seeding/configuration, platform-admin authorization and MFA checks, admin frontend route, dashboard token handling, Docker demo image, Render demo blueprint, and demo deployment instructions.

## Critical finding in Increment 53

The customer demo and platform-owner demo were seeded as the same `DEMO_EMAIL` user. Since the backend intentionally recognizes the demo identity as a platform owner, a customer demo session could also call platform-admin APIs. The two frontend URLs did not represent separate security identities.

## Corrections made

- Split identities and workspaces:
  - Customer: `DEMO_EMAIL` (default `customer-demo@example.com`), password `DEMO_PASSWORD` (default `pass`).
  - Platform owner: `DEMO_ADMIN_EMAIL` (default `platform-owner-demo@example.com`).
- Added configuration validation preventing the two demo emails from being equal, case-insensitively.
- Updated the platform-admin identity helper and `POST /api/v1/auth/demo-admin` to recognize only `DEMO_ADMIN_EMAIL`.
- The administrator demo user has `has_password=false` and a random password hash reset at startup. It can only obtain a session through the separate demo endpoint; the known customer demo password cannot sign in as the platform owner through `/login`.
- Removed `PLATFORM_ADMIN_EMAILS=admin@example.com` from `backend/Dockerfile.demo`. The demo owner is recognized through the narrowly scoped demo identity check, not a broad email allowlist.
- Changed the customer login CTA to **Enter customer demo**.
- Added a complete administrator credential form at `/admin/login` for configured real administrators, including the authenticator code field. The demo shortcut appears only when the backend reports demo mode.
- Changed unauthenticated `/platform` access to return to `/admin/login` rather than the customer login page.
- Corrected demo setup documentation and handover notes.

## Demo URLs and expected behavior

- Customer sign-in: `/login` → customer demo workspace.
- Administrator sign-in: `/admin/login` → **Enter administrator demo** → `/platform`.
- Real configured administrators can use email, password and TOTP on `/admin/login` when demo mode is off.
- API demo owner entry: `POST /api/v1/auth/demo-admin`.
- Customer demo tokens must receive `403` from `/api/v1/platform-admin/*` endpoints.
- Demo owner tokens can access platform-admin endpoints without TOTP only while `DEMO_MODE=true` on an isolated SQLite database.

## Verification performed

- `python -m compileall -q backend/app backend/tests backend/migrations backend/scripts` — passed.
- Focused authentication/demo tests: `39 passed` across `test_auth.py`, `test_auth_sessions.py`, `test_admin_demo_access.py`, and `test_demo_mode.py`.
- The focused test command used a temporary local `pyotp` import stub because `pyotp` is absent from this execution environment. The tested demo flows do not validate real TOTP generation/verification; production MFA still needs a dependency-complete run.
- Direct demo seeding smoke test using a fresh SQLite file — passed. It created two distinct users and two workspaces; the customer identity has a password, while the admin identity has `has_password=false`.
- TSX syntax transpilation for the changed admin login, customer login and platform dashboard files — passed.
- ZIP integrity — to be checked after packaging.

## Remaining verification gaps / deployment blockers

- Full backend suite and the existing platform-admin/billing suites are not green in this environment. The latter currently have nine failures because their legacy test fixtures authenticate owner accounts without enrolling MFA, while the current platform-admin policy requires MFA. Do not weaken the application MFA requirement to make those fixtures pass; update the fixtures in a dependency-complete CI run.
- No frontend `node_modules` directory is present. `npm run typecheck` was attempted and is blocked by missing `next`, `react`, `@types/node`, `vitest` and related package declarations; `npm ci`, lint, Next.js production build and browser/mobile QA remain unverified. Changed TSX files passed a TypeScript transpile/syntax check only.
- No live Render/Vercel deployment was tested. Deploy this ZIP to the demo services before testing hosted URLs.
- Render free-instance filesystem is ephemeral; the demo SQLite database may reset on restart/sleep. Do not store real customer data in demo mode.
- Demo mode must remain `APP_ENV=staging` (or development), `DEMO_MODE=true`, and SQLite. Never use `Dockerfile.demo` for production.

## Release recommendation

The customer/admin demo identity separation and the separate administrator sign-in route are corrected in source. The archive is suitable for the next isolated demo deployment and manual acceptance testing, but this audit does **not** certify a production release. Complete frontend build/browser checks and a dependency-complete backend CI run before treating the project as release-ready.
