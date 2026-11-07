# Increment 53 — Separate platform administrator demo access

Date: 2026-11-07

## User goal

Keep the customer demo working without registration and provide a separate URL where the project owner can explore the platform administrator dashboard without configuring production credentials or enrolling an authenticator solely for demo testing.

## Delivered

- Customer demo is preserved at `/login`; the existing `/api/v1/auth/demo` discovery and seeded account are unchanged.
- `/admin/login` is now a functional, separate administrator entry page. When demo mode is enabled it displays **Enter administrator demo** and redirects to `/platform` after receiving a demo session.
- Added `POST /api/v1/auth/demo-admin`. It is unavailable (404) unless `DEMO_MODE=true`; it issues a session only to the active, verified user matching `DEMO_ADMIN_EMAIL`, and only when that user has a seeded workspace membership.
- The separate administrator demo identity is recognized as the platform owner by backend authorization. A narrowly scoped MFA exception applies only to that identity while demo mode is enabled. The shared `require_platform_admin` dependency continues to require MFA for all other platform administrators.
- The separate administrator demo identity has no usable password credential; its random password hash is reset at startup and `has_password=false`. It can only obtain a demo session through the dedicated demo endpoint. Production owner and delegated admin MFA rules remain unchanged.
- Added regression tests for demo owner access to the real overview API without MFA, disabled endpoint behavior outside demo mode, denial of platform admin access to a normal customer, and denial of password login for the separate admin demo identity.

## How to test

1. Start the backend with `DEMO_MODE=true` and `APP_ENV` set to `development` or `staging` (never `production`). The demo startup seeding creates both `DEMO_EMAIL` (customer) and `DEMO_ADMIN_EMAIL` (platform owner), each with a separate workspace.
2. Open `http://localhost:3000/admin/login` (or the corresponding deployed demo frontend URL).
3. Select **Enter administrator demo**. The app should redirect to `/platform`. For a real configured administrator outside demo mode, use the password and authenticator fields on this same page.
4. Open `http://localhost:3000/login` to test the customer demo independently.

The admin demo API route is `POST /api/v1/auth/demo-admin`; it is not a browser page. The administrator page URL is `/admin/login` and the dashboard URL is `/platform`.

## Security boundaries

- `DEMO_MODE=true` is refused when `APP_ENV=production` and now requires an SQLite database, preventing accidental connection to shared PostgreSQL customer data.
- The demo session endpoint is not available outside demo mode.
- The server verifies the configured demo identity and active/verified state; the frontend does not grant authorization.
- The MFA exception is not available to normal owner allowlist accounts or delegated administrator roles.
- Demo admin capabilities operate on the demo deployment's database. Do not point a demo deployment at production customer data.

## Verification

Python compilation passed. Focused pytest execution was attempted but collection stopped because `pyotp` is not installed in this environment. Frontend dependencies are not installed, so the Next.js production build and browser QA were not run. Live deployment was not tested.
