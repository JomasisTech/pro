# AutoBizPro Design References

These screenshots are the project's visual references. Read this document before building or redesigning frontend pages.

## Reference images

- `01-desktop-dark-mode-reference.png` — primary visual direction and primary dark-theme reference.
- `02-mobile-dark-mode-reference.jpg` — mobile layout and responsive behavior reference. Keep the same brand identity as desktop; do not copy its color balance blindly.
- `03-desktop-light-mode-reference.png` — light-theme reference.

The screenshots are guidance, not pixel-perfect templates. Different product pages should have layouts suited to their tasks while retaining the same design language.

## Brand direction

- Primary brand: purple / indigo.
- Dark surfaces: deep navy, with slightly lighter navy cards and subtle blue-gray borders.
- Light surfaces: white and pale blue-gray.
- Main text: near-white in dark mode; deep navy in light mode.
- Secondary text: muted blue-gray.
- Semantic accents: green for success, blue for information, amber/orange for warnings or scheduled states, red for destructive/error states, pink where useful for data-series differentiation.
- Use gradients sparingly, mostly for emphasis rather than every surface.
- Use consistent rounded corners, spacing, typography, focus rings, and hover states.

## Design tokens

Define colors once in the shared global stylesheet (CSS custom properties) and map Tailwind utilities to those tokens where supported by the project's Tailwind version. Components should consume semantic tokens, not scatter raw hex values throughout the code.

Suggested starting tokens (adjust only in the central token definition):

```css
:root {
  color-scheme: light;
  --color-brand: #4f46e5;
  --color-brand-strong: #5b35f5;
  --color-brand-soft: #ede9fe;
  --color-page: #f5f7fc;
  --color-surface: #ffffff;
  --color-surface-raised: #f8faff;
  --color-border: #e2e8f0;
  --color-text: #0f172a;
  --color-text-muted: #64748b;
  --color-success: #10b981;
  --color-info: #0ea5e9;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-accent-pink: #ec4899;
}

[data-theme="dark"] {
  color-scheme: dark;
  --color-brand: #6d4aff;
  --color-brand-strong: #7c3aed;
  --color-brand-soft: #31205f;
  --color-page: #0b1020;
  --color-surface: #11182b;
  --color-surface-raised: #171f35;
  --color-border: #28324e;
  --color-text: #f8fafc;
  --color-text-muted: #a7b2cc;
  --color-success: #10b981;
  --color-info: #0ea5e9;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-accent-pink: #d946ef;
}
```

These are initial design tokens inferred from the references, not a claim that the original product used these exact color values. Keep the source of truth centralized. Components should use semantic names such as `bg-[var(--color-surface)]` or small reusable component classes rather than literal colors.

## Implementation rules

1. Put shared design tokens in one place, preferably `frontend/src/app/globals.css` for this project.
2. Use semantic CSS variables for brand, page, surface, border, text, and status colors. Avoid repeating hex values across pages.
3. If the Tailwind configuration supports theme mapping, map semantic Tailwind names to the CSS variables. Otherwise use a small, consistent set of CSS-variable utilities or component classes.
4. Build reusable primitives for buttons, cards, inputs, badges, navigation items, dropdowns, and page headings.
5. Use the same tokens for desktop, tablet, and mobile. Responsive layouts may change structure, not brand identity.
6. Theme-specific differences belong in the theme token layer, not scattered conditional colors in individual pages.
7. Keep accessible contrast, visible keyboard focus, disabled states, loading states, empty states, and error states.
8. Use amber for warnings/approval attention sparingly; it should not overpower the purple/indigo brand.
9. Avoid hardcoding sample metrics or fake account states as if they were live data. Clearly identify placeholders until real API integration exists.
10. Do not create every future product page in advance. Follow the active scope in `docs/project-management/project-status.md` and implement one verified vertical slice at a time.

## Responsive guidance

- Desktop: persistent side navigation, clear page header, dashboard cards and charts arranged in a balanced grid.
- Mobile: compact top bar, touch-friendly controls, two-column metric cards where space allows, readable stacked content cards, and a fixed bottom navigation only where appropriate.
- Prevent horizontal overflow; test narrow widths and long content.
- Ensure the primary action remains easy to find on both screen sizes.

## AI / contributor checklist

Before implementing a page:
- Read this guide and inspect all three references.
- Read `AGENTS.md`, `docs/project-management/master-development-prompt.md`, and `docs/project-management/project-status.md`.
- Reuse existing tokens and components.
- Keep the page creatively suited to its job; do not copy the dashboard layout mechanically.
- Verify light and dark themes and mobile responsiveness.
- Report which files changed and which checks were actually run.
