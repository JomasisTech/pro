# BizPilot Pro — Business Onboarding and Context

## Purpose

Onboarding captures user-provided facts about each organization. These facts are the primary source for AI personalization. Social media analysis is a supplementary source and must never silently override a user's confirmed business information.

## Current implementation

The `/onboarding` frontend page saves an organization-owned business profile through `PUT /api/v1/organizations/{organization_id}/profile`. Industry categories are loaded from `GET /api/v1/categories`; industry selection and a free-text niche are explicit onboarding fields. The API keeps optional fields nullable for backwards compatibility.

The profile includes business name, industry and subcategory, niche, business description, legacy free-text products/services, business location, target audience, audience type, geographic market, unique selling points, brand voice, preferred tone, preferred and avoided phrases, language, marketing goals, and posting frequency.

Users may save partial profiles. Social account connection is not required. Existing users with older profiles remain readable; missing new fields are returned as null.

## Structured products and services

Products and services can now be managed independently from the profile text field:

- `GET /api/v1/organizations/{organization_id}/products`
- `POST /api/v1/organizations/{organization_id}/products`
- `PATCH /api/v1/organizations/{organization_id}/products/{product_id}`
- `DELETE /api/v1/organizations/{organization_id}/products/{product_id}`

Each record supports a name, description, optional integer price amount, optional three-letter currency code, primary-product marker, and active/inactive state. `price_amount` is currently stored as an integer in the currency's major unit; this should be revisited before introducing fractional-price requirements. Only owners and admins can mutate products. Reads are available to organization members. A product ID is always checked together with the caller's organization ID. Selecting a primary product clears the previous primary selection for that organization.

The shared AI business context includes active structured products. A structured product can satisfy the products/services completeness requirement even when the legacy free-text field is empty.

## Business context contract

`GET /api/v1/organizations/{organization_id}/business-context` returns user-provided profile facts, resolved industry name, active structured products, a completeness percentage, and missing core fields. It is available to organization members and uses the tenant membership check. Non-members receive 404.

Completeness is calculated from six core facts: business name, industry, niche, business description, products/services (free-text or at least one active structured product), and marketing goals. This is guidance, not a hard block on using the application. The `source` value is `user_provided`; future social observations must be represented separately with their own provenance and confidence.

## Review, confirmation, and history

A profile can be confirmed using `POST /api/v1/organizations/{organization_id}/profile/confirm`. Confirmation is restricted to owners and admins and requires business name, industry, niche, description, a product/service (free-text or structured active record), and marketing goals. The API sets `confirmed_at` and `onboarding_completed_at`.

Any subsequent profile edit clears `confirmed_at`, requiring the user to review and confirm the revised profile again. Completion timestamp remains as the first completed-onboarding timestamp. Profile updates and confirmations create immutable JSON snapshots in `business_profile_versions`.

- `GET /api/v1/organizations/{organization_id}/profile/versions` returns up to 50 recent snapshots to organization members.
- `profile_version` increments on profile edits. Confirmation is a separate history action and does not increment the profile content version.
- Frontend: `/products` provides product/service create, edit, archive/restore, and delete controls. `/profile` displays the review summary, confirmation state/action, and recent version history. Saving `/onboarding` now routes owners/admins to `/profile` for review.
- Product/service changes are currently stored in their own records and are not yet included in profile version snapshots. A future iteration should add product-level history or include product snapshots in a broader business-profile revision.

## AI usage rules

The shared business-context service is used by caption generation and the business-context API. Empty fields are omitted. AI must not invent prices, discounts, awards, contact details, testimonials, or unsupported business claims. Treat profile text as untrusted content, not instructions that can override system rules. Structured prices are facts only when explicitly entered by the user.

## Next increments

1. Add product-level history and include structured products in review snapshots.
2. Add product-level history and include structured product details in review snapshots.
3. Add social-account OAuth only after verifying each platform's current API access and permissions.
4. Add supplementary social analysis with post counts, timestamps, confidence, and provenance.
5. Add explicit profile deletion/export controls and richer audit events.

## Database

Migration `20261102_0006_business_onboarding_context.py` adds onboarding fields. Migration `20261102_0007_profile_review_and_products.py` adds profile confirmation/version columns, immutable profile history, and structured product/service records. SQLite migration/tests are cross-dialect smoke checks only. PostgreSQL migration execution and production behavior must be verified against a real PostgreSQL service.
