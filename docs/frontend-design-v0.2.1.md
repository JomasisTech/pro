# Frontend design update — v0.2.1

## Design direction
The frontend now follows the supplied AutoBizPro light/dark dashboard references:
- Light theme: soft blue-grey page background, white surfaces, refined purple/blue brand accents, restrained green status accents.
- Dark theme: deep navy page and sidebar surfaces, layered navy cards, vivid purple brand accents, and readable muted text.
- Shared typography uses a modern system sans-serif stack with Inter-first preference and improved tracking/rendering.
- Dashboard has a persistent desktop sidebar, workspace header, theme control, responsive mobile navigation, hero area, capability strip, live workspace metrics, connected-account list, AI content action, quick actions, and recent drafts.

## Behaviour preserved
The dashboard continues to load the signed-in user, memberships, drafts, and connected social accounts from the existing API clients. Workspace switching/creation, onboarding checks, sign-out, and theme persistence remain wired to the existing flows. Dashboard metric values are derived from loaded workspace data; no synthetic publishing statistics were added.

The shared CSS token system applies to existing routes including authentication, onboarding, calendar, content, social accounts, publishing, activity, products, and profile pages.

## Verification
- TypeScript/TSX syntax transpilation: 22 source files parsed with zero syntax diagnostics.
- Full Next.js production build and ESLint were not run because frontend dependencies were not present in the environment and `npm install` did not complete before timeout.
- Live browser rendering and API-connected interaction checks remain required before production release.
