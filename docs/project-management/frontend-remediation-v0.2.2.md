# Frontend remediation — v0.2.2

Date: 2026-11-02

## Scope

This update addresses source-code and product-quality issues identified in the v0.2.1 archive. It does not claim live provider, database, deployment, or browser verification. Backend APIs, migrations, publishing workers, and database contracts were not changed.

## Changes

- Added a shared authenticated-page application chrome with persistent desktop navigation, consistent page header, theme toggle, create-content shortcut, and mobile bottom navigation. Login, registration, onboarding, social OAuth callback, and the dashboard retain their dedicated layouts.
- Improved the dashboard desktop metric layout so all four workspace metrics sit in one row at wide widths.
- Added a mobile-friendly “Needs your review” panel backed only by real drafts whose status is `draft`; no synthetic approval records are created.
- Replaced the nonfunctional dashboard search decoration with a working client-side filter for loaded draft titles/content/status and connected social account names/providers.
- Linked the notifications affordance to the real activity log instead of leaving it inert.
- Replaced the misleading upgrade CTA with a business-profile shortcut because billing/upgrade flows are not implemented.
- Removed capability claims for future products (lead management, email marketing, analytics and advanced automation); the dashboard now highlights only implemented Product 01 capabilities.
- Removed inline capability-icon colors and moved the styling to theme-aware design tokens.
- Standardized customer-facing frontend branding and API error copy on AutoBizPro, consistent with the supplied design references.
- Bumped the frontend package version to 0.2.2. Backend package/version and API contracts remain unchanged.

## Verification

- `tsc --noEmit` was attempted. It cannot complete because frontend dependencies (`next`, `react`, and their type declarations) are not installed in this environment. The command did identify and allowed correction of one malformed import line introduced during editing; after correction, remaining diagnostics are dominated by missing dependencies and JSX typings.
- `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` was attempted but timed out because package registry access was unavailable. No lockfile was fabricated. Generate and commit `frontend/package-lock.json` in a network-enabled environment, then use `npm ci` in CI.
- ESLint, Next.js production build, browser rendering, and responsive interaction tests could not be run without installing dependencies.
- No live database, social provider, OAuth, worker, or deployment tests were attempted; those remain explicitly outside this code-only remediation.

## Remaining code-level work

- Search currently filters dashboard data already loaded for the active workspace; it is not a global cross-page search.
- Drafts have only `draft`, `approved`, and `rejected` statuses in the current API type. The review panel therefore uses the truthful label “Needs your review” and only surfaces actual `draft` records.
- Analytics charts and upcoming schedule widgets were not fabricated. They should be added when the relevant reliable analytics and scheduled-post data are available to the dashboard.
- Session hardening and distributed rate limiting remain backend security work and were not changed in this frontend-focused update.
