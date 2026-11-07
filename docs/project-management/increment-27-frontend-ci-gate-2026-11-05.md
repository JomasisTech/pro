# Increment 27 — Frontend CI verification gate

**Date:** 2026-11-05  
**Baseline:** `bizpilotpro-remediation-2026-11-05-increment-26.zip`  
**Scope:** Improve frontend verification automation without changing product behavior.

## Changes

1. `frontend/package.json`: added `typecheck` script running `tsc --noEmit`.
2. `.github/workflows/ci.yml`: added a dedicated TypeScript type-check step after ESLint and before the production build.
3. Fixed two frontend runtime defects discovered during the dependency-blocked static TypeScript pass: `billing/page.tsx` now captures the fourth result (`actions`) returned by its four-request `Promise.all`; `platform/page.tsx` now captures the fifth result (`topData`) returned by its five-request `Promise.all`. Both pages previously referenced variables that were never declared.
4. `README.md`: documents lint, type-check, and build commands and warns that `npm ci` is not appropriate until a reviewed lockfile exists.
5. Project-management status, known-issues, completed-work, and handover documents updated.

No backend code, database models, or migrations were changed.

## Verification

| Check | Result | Evidence / limitation |
|---|---|---|
| `frontend/package.json` JSON parse | Passed | Parsed with Python's JSON parser after edit. |
| Billing/platform Promise.all tuple fixes | Static check passed | Each awaited Promise.all now destructures the same number of results as the number of requests; no remaining TS2304 undefined-name diagnostics were reported by the globally available TypeScript compiler. |
| Runtime/dev import scan | Passed | Imports resolve to `next`, `react`, `@eslint/eslintrc`, local `@/` modules, CSS, or Node built-ins. This is a dependency declaration scan, not a compiler check. |
| npm lockfile generation | Blocked | `npm install --package-lock-only --ignore-scripts --no-audit --no-fund --fetch-retries=0 --fetch-timeout=20000` failed because DNS could not resolve `registry.npmjs.org` (`EAI_AGAIN`). npm cache is empty. |
| `npm run lint` | Not run | ESLint is not installed; dependency installation is blocked. |
| `npm run typecheck` | Attempted, blocked | A globally installed TypeScript 5.8.3 ran, but the project packages and React/Next/Node type declarations are absent. It emitted missing-module/JSX/type diagnostics (2,906 lines); this is not a valid project type-check result. No remaining TS2304 undefined-name diagnostics appeared after the two fixes. |
| `npm run build` | Not run | Next.js is not installed; dependency installation is blocked. |
| GitHub Actions | Not run | Workflow was updated but no remote CI run was available. |
| Browser/mobile QA | Not run | Requires a built/running frontend and browser session. |

## Why no lockfile was added

A lockfile must contain the real resolved dependency graph, versions, integrity hashes, and package metadata. It cannot safely be invented from the top-level `package.json`. This environment has no cached package metadata and registry DNS failed, so no synthetic lockfile was created.

## Required next actions

Run in a network-enabled environment with Node 22 and npm 10:

```bash
cd frontend
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
# Review package-lock.json, then commit it with package.json.
npm ci
npm run lint
npm run typecheck
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run build
```

After the lockfile is committed, change the frontend CI install step from `npm install` to `npm ci` so CI uses the exact reviewed dependency graph. Fix any actual lint, type, or build failures in a separate reviewed patch, preserving existing UI and behavior.

## Completion assessment

Increment 27 is complete as a frontend CI configuration and targeted defect-fix increment. Frontend stabilization itself is **not complete**. Product 01 is not certified as a working MVP or production-ready based on this increment.
