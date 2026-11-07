# Categories and Business Profile API (initial implementation)

All routes require `Authorization: Bearer <access_token>`.

| Method | Path | Who can call | Result |
| --- | --- | --- | --- |
| GET | `/api/v1/categories` | any signed-in user | Industries, each with nested `subcategories`, ordered for display |
| GET | `/api/v1/organizations/{organization_id}/profile` | any member | The business profile, or `404` until one is saved |
| PUT | `/api/v1/organizations/{organization_id}/profile` | `owner` or `admin` | Creates or **fully replaces** the profile; returns it |
| GET | `/api/v1/organizations/{organization_id}/business-context` | any member | Returns user-provided business facts, industry name, completeness percentage, and missing core fields |

## Profile fields
`business_name` (required, 2–160), `industry_id`, `niche` (≤160), `subcategory_id`, `description` (≤2000), `products_services` (≤2000), `location` (≤160), `target_audience` (≤1000), `audience_type` (`consumers`, `businesses`, or `both`), `geographic_market` (≤160), `unique_selling_points` (≤1500), `brand_voice` (≤500), `preferred_tone` (≤120), `preferred_words` (≤1000), `avoided_words` (≤1000), `language` (required, default `en`), `marketing_goals` (≤1000), and `posting_frequency` (≤64). Text is trimmed; blank optional text is stored as `null`. Omitted optional fields are cleared (PUT semantics). The frontend requires an industry and free-text niche, while the API keeps them nullable for compatibility with existing clients and older profiles.

## Rules
- Business context completeness is guidance, not a hard block; the six core facts are business name, industry, niche, description, products/services, and marketing goals.
- Business context is explicitly marked `user_provided`; future social observations must be stored separately with provenance and confidence.
- A subcategory requires an industry, the industry must be a top-level category, and the subcategory must belong to that industry; otherwise `400`.
- Non-members get `404`; members without `owner`/`admin` get `403` on PUT (same rules as `docs/organizations-api.md`).
- Categories are stored in the `industry_categories` table (one table; `parent_id` is null for industries). Starter data (10 industries, 34 subcategories) is inserted by migration `20261102_0002` with deterministic ids. The frontend loads the list from the API and never hardcodes it.

## Frontend
`/onboarding` (linked from the dashboard sidebar as "Business Profile") loads categories and the saved profile, and saves through PUT. It shows a read-only notice to plain members.

## AI brand voice controls (Increment 31)

The profile now includes two additional owner-controlled fields:

- `brand_voice_mode`: `hybrid` (default), `automatic`, or `manual`.
- `custom_ai_instructions`: optional owner-written generation guidance, maximum 2,000 characters.

The profile remains a full-replacement `PUT`, so clients should send both fields. Existing rows are migrated to `hybrid`.

Mode behavior in caption and video-script generation:

- `automatic`: include the latest owner/admin-approved Brand Intelligence proposal as writing-style guidance; do not include a pending or rejected proposal.
- `manual`: ignore social-derived voice proposals and use the owner's explicit `brand_voice`, `preferred_tone`, `preferred_words`, and `avoided_words` fields.
- `hybrid`: combine the latest approved social-derived voice proposal with the owner's explicit writing preferences.

`custom_ai_instructions` is passed as a separate owner-preference section in the generation prompt for all three modes. It is style guidance only and cannot override factual accuracy, safety, or platform rules. Confirmed business facts (industry, niche, products/services, audience, etc.) remain sourced from the owner-maintained profile and are never overwritten by Brand Intelligence.

A change to the business profile increments its version and clears `confirmed_at`, requiring the owner/admin to review and confirm the changed business facts again. The `brand_voice_mode` and custom instructions are included in the same version snapshot.
