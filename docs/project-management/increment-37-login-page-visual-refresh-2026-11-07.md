# Increment 37 — branded login page visual refresh — 2026-11-07

- Reworked `/login` into a branded sign-in experience using a deep purple page canvas, a darker purple desktop story panel, and a pale lavender form surface.
- Added restrained radial glow/orbit decoration, a responsive mobile brand header, and a clearer heading/intro hierarchy.
- Preserved existing email/password authentication, demo-mode sign-in, social sign-in, error messaging, `next` redirect validation, forgot-password and registration links.
- Added centralized auth-page palette tokens and styling in `frontend/src/app/globals.css`; the lavender form uses fixed high-contrast text tokens so the form remains legible when the app's dark theme is selected.
- No backend, authentication, or API behavior was changed.

**Verification:** `git diff --check` and source inspection only. Frontend dependencies are not installed in this environment, so ESLint, TypeScript, Next.js build, and browser/mobile visual QA were not run.
