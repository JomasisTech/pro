# Increment 38 — dashboard profile control and KPI polish (2026-11-07)

## Changes

- Replaced the detached dashboard workspace-chevron button with one integrated, branded initials-and-chevron control. The avatar and disclosure indicator now share a single clickable hit target, including on mobile.
- Added a compact profile/workspace dropdown containing the signed-in identity, business profile, workspace settings, account security, workspace switching/creation, and sign-out actions.
- Added Escape-key and outside-pointer dismissal for the dropdown; navigation actions close it, and the current workspace is visibly marked.
- Preserved the existing organization switching/creation functions and the existing sign-out flow; no authentication API or session behavior was changed.
- Reaffirmed the KPI card layout: icon remains in the left column, value/label/status remain to its right, and the chevron remains in the upper-right corner. Tightened small-screen spacing so the chevron does not collide with longer labels such as “Connected accounts.”
- Audited the dashboard's literal icon references against the shared dashboard icon path map; the KPI and panel icon names used by the dashboard are mapped.

## Files changed

- `frontend/src/app/page.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/app/dashboard.css`
- `docs/project-management/project-status.md`
- `docs/project-management/increment-38-dashboard-profile-control-and-kpi-polish-2026-11-07.md`

## Verification

- Source-level checks confirm the old detached workspace-options button is gone and the new integrated profile control and menu dismissal handlers are present.
- Dashboard KPI markup and icon mapping were inspected; all dashboard icon names used in KPI/panel sections resolve through the shared icon map.
- TypeScript `transpileModule` syntax validation passed for `frontend/src/app/page.tsx`. A structural regression script passed checks for the integrated trigger, menu actions, dismissal handlers, KPI columns, mobile spacing, focus styling, and removal of the detached arrow.
- A full `tsc --noEmit -p frontend/tsconfig.json` attempt was blocked by missing installed dependencies/types (`next`, `react`, `vitest`, and `@types/node`); the resulting JSX/type errors are dependency-resolution fallout and do not establish a clean project typecheck.
- ESLint, Next.js build, Vitest, and browser/mobile interaction checks remain unverified because this extracted source archive does not include `frontend/node_modules` or a generated `frontend/package-lock.json`. The archive is not a Git checkout, so `git diff --check` is unavailable; changed files were checked for trailing whitespace separately.
