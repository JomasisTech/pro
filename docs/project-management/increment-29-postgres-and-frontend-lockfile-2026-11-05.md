# Increment 29 — PostgreSQL integration safety and frontend lockfile verification

**Date:** 2026-11-05  
**Base:** Increment 28  
**Scope:** Foundation verification only. Product 01 remains active; future products remain out of scope.

## Implemented

- Added an explicit safety gate to `backend/tests/test_postgres_integration.py` before either destructive PostgreSQL integration test can drop/recreate the SQLAlchemy metadata tables.
- The destructive tests now require `TEST_POSTGRES_ALLOW_DESTRUCTIVE=1`, a local test host (`localhost`, `127.0.0.1`, or the CI service host `postgres`), and a database named `ci_db` or prefixed `test_`.
- Added three unit tests for the guard: missing opt-in, production-like database name, and remote host are rejected.
- Updated `.github/workflows/ci.yml` to set the destructive-test opt-in only inside the isolated PostgreSQL 16 CI job, whose service database is `ci_db`.
- Inspected the frontend manifest and confirmed Node 22.16.0/npm 10.9.2 match the project's documented lockfile-generation target.

## Verification performed

- All 51 backend test files, split into two bounded groups: **364 passed, 3 skipped** (178 passed in group 1; 186 passed and 3 skipped in group 2).
- Focused PostgreSQL guard/connectivity file run: **3 passed, 3 skipped**. The three skipped tests require a real `TEST_POSTGRES_URL`; no PostgreSQL service is available in this runtime.
- `python -m compileall -q app tests migrations` — passed.
- File-backed SQLite Alembic migration test: upgrade to head (`20261104_0039`), downgrade to `20261104_0038`, re-upgrade to head, and `alembic check` — passed; no new operations detected.
- Static inspection confirms GitHub Actions declares `postgres:16`, runs backend tests with `TEST_POSTGRES_URL`, then applies Alembic migrations to that PostgreSQL service. The workflow itself was not executed here, so PostgreSQL 16 behavior is **not yet verified**.

## Frontend lockfile — attempted, not completed

- `frontend/package.json` declares Next.js `^15.5.0`, React/React DOM `^19.1.0`, TypeScript `^5.8.0`, ESLint 9 and Tailwind CSS 4 dependencies.
- The archive did not contain `frontend/package-lock.json` or `frontend/node_modules`.
- Attempted genuine lockfile generation with Node 22.16.0/npm 10.9.2 using `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` and a bounded retry with zero fetch retries and a 12-second fetch timeout. Both attempts timed out; npm's log showed DNS resolution failure (`EAI_AGAIN registry.npmjs.org`).
- No synthetic or hand-written lockfile was created. `package-lock.json` remains outstanding. Since dependencies could not be resolved, `npm ci`, ESLint, TypeScript project checking, Next.js production build, and browser/mobile QA were not run.
- Once registry access is available, generate the lockfile from `frontend/package.json` with Node 22/npm 10, review the diff, then verify `npm ci`, `npm run lint`, `npm run typecheck`, and `npm run build`. Only after the lockfile is committed should the frontend CI install step change from `npm install` to `npm ci`.

## PostgreSQL 16 limitation and safety note

The destructive integration tests recreate all tables in `Base.metadata`; they must only run against an isolated disposable test database. The new guard reduces accidental misuse but is not a substitute for keeping production credentials out of `TEST_POSTGRES_URL`. This environment has no Docker, `psql`, or `pg_isready` executable, and its Python environment lacks the `psycopg` driver, so no local PostgreSQL 16 test or migration was run. The PostgreSQL 16 GitHub Actions service remains the intended verification environment; inspect the actual CI run before declaring this gate passed.

## Remaining blockers

1. Generate and commit a genuine `frontend/package-lock.json` when npm registry DNS/network access works.
2. Run frontend `npm ci`, lint, TypeScript check, production build and browser/mobile QA.
3. Observe a successful GitHub Actions PostgreSQL 16 integration test and migration run.
4. Continue with the other owner-side release checks already listed in `HANDOVER.md` (SMTP delivery, live Paystack test mode, scheduler supervision and provider verification).

**Outcome:** Backend regression coverage and destructive-test safeguards improved. SQLite migration integrity is rechecked. The requested lockfile was attempted but could not be generated because npm registry DNS was unavailable; PostgreSQL 16 remains CI-gated and unverified in this execution environment. No production database or live service was touched.
