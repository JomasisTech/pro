# Product 02 — Lead Management and AI Lead Generation Requirements

**Status:** Approved product direction / requirements captured; not implemented or scheduled for active development yet.  
**Current platform scope:** Product 01 and foundation hardening remain the active delivery scope.  
**Related requirements:** Product 04 Email Marketing, Product 06 Data Collection, and `docs/architecture/background-job-progress.md`.

## 1. Product objective

Enable a customer to describe the businesses they want to reach, discover relevant businesses from permitted sources, extract and enrich publicly available business contact information, clean and qualify the resulting records, and prepare high-quality leads for an outreach workflow.

The system must not promise a fixed number of leads or guaranteed email deliverability. Results depend on source coverage, source permissions, public data availability, geography, and verification coverage.

## 2. Customer workflow

A customer starts a lead-generation job by providing:

- Industry and optional niche (for example, automotive repair, car dealerships, or digital marketing agencies).
- Target geography (country, region, city, or service area).
- Business type and optional company-size range, where reliable data is available.
- Ideal-customer description and qualification criteria.
- Desired lead count or search limit.
- Optional exclusions (existing customers, competitors, certain domains, already-contacted leads).
- Intended offer or reason for outreach, used later for relevance and message generation.

The customer reviews the search summary before starting. The system validates the request, estimates likely source coverage where possible, explains usage limits, and creates a durable background job.

## 3. Lead-generation pipeline

The pipeline is a sequence of independently observable stages. Stages may be skipped when they do not apply, but the system must record why.

1. **Request understanding and target identification** — normalize the customer's industry, niche, geography, company type, exclusions, and qualification rules. Ask for clarification when the request is materially ambiguous rather than silently guessing.
2. **Business discovery** — search permitted search APIs, licensed business datasets, approved directories, and accessible public company websites. Preserve the source and discovery timestamp for each result.
3. **Contact extraction and enrichment** — extract business name, canonical website/domain, public business email, public phone number, location, category, source URL, and other permitted business-level fields. Distinguish general inboxes (such as info@) from named business contacts. Do not infer or fabricate an email address from a person's name or domain.
4. **Normalization and deduplication** — canonicalize domains and email addresses; merge duplicate businesses and contacts with deterministic rules; retain source provenance and merge history.
5. **Email quality checks** — validate syntax, domain, MX availability, disposable-domain risk, role-account classification, and supported verification-provider results. Use statuses such as `valid`, `invalid`, `risky`, `unknown`, and `not_checked`. DNS/MX checks do not prove that a mailbox exists or accepts mail. Do not use aggressive SMTP mailbox probing as a default verification method.
6. **Lead qualification and scoring** — apply transparent rule-based criteria and AI-assisted relevance analysis. Save a score, score explanation, evidence references, confidence, and qualification version. AI must not invent evidence; low-confidence leads should be labelled for review.
7. **Lead review and storage** — show results in a customer-controlled table with filters, source links, verification status, score, and exclusion controls. Customer can accept, reject, tag, export, or add leads to an existing contact record, subject to permissions and plan limits.
8. **Outreach handoff** — eligible leads may be selected for Product 04 outreach preparation. This handoff does not itself authorize sending. Consent/lawful-basis, suppression, unsubscribe, campaign, and customer approval checks must be enforced by the email/campaign workflow.

## 4. Lead record and provenance requirements

A lead should support (as applicable): organization ID, business name, industry/niche, website, normalized domain, business description, country/region/city, public business email, email classification and verification status, public phone, source URLs, source type, discovered-at timestamp, last-checked timestamp, confidence, qualification score, score explanation, customer notes, tags, lifecycle status, suppression status, and links to related contact/campaign records.

Every material extracted or AI-enriched field must retain provenance: source URL/provider, observed timestamp, extraction method, and confidence where applicable. Never overwrite customer-confirmed data with scraped or AI-inferred data without explicit review.

Store only data needed for the stated business purpose. Apply retention, correction, deletion, export, and suppression policies appropriate to applicable law and provider terms.

## 5. Lead scoring

Scoring must be explainable and configurable. It may consider industry fit, geography fit, business-type fit, evidence of relevant need, website/business activity, and completeness/reliability of contact data. Separate:

- **Fit score:** how closely the business matches the customer's ideal customer profile.
- **Data quality:** how complete and reliable the record is.
- **Contactability:** the quality/verification state of the available business contact route.

Do not collapse these into a single unexplained number. Display score explanations and allow customers to filter by each dimension. Avoid sensitive personal attributes and protected-class inference.

## 6. Customer interface requirements

The frontend must provide:

- A guided search form with target criteria and exclusions.
- A clear search summary and confirmation before the job starts.
- A live pipeline progress view (see `docs/architecture/background-job-progress.md`).
- A results table with pagination, filters, sorting, source links, and bulk actions.
- Visible counts for discovered businesses, extracted contacts, duplicates removed, valid/invalid/risky/unknown emails, qualified leads, and errors where applicable.
- A clear distinction between stage completion, partial results, skipped stages, and failure.
- Safe retry/resume behaviour that does not duplicate leads or repeat costly external operations unnecessarily.
- Export controls and plan/usage information.
- Accessible responsive UI, including mobile layouts.

The user must be able to navigate away and return later without losing job status or results. Progress must be durable, not held only in browser memory.

## 7. AI architecture

Use the existing AI provider abstraction. One capable model may perform multiple specialised reasoning tasks through separate structured prompts/calls; the architecture must not require a different model for every stage or a multi-agent framework. Keep stages logically separate so they can be retried, tested, measured, and replaced independently.

Use deterministic code for normalization, deduplication, syntax checks, policy enforcement, limits, and state transitions. Use AI for ambiguous classification, qualification explanations, and natural-language interpretation where it adds measurable value. Validate model output against schemas and source evidence. Treat web pages and scraped text as untrusted input, never as instructions to the model or worker.

## 8. Safety, privacy, and source compliance

- Use official APIs, licensed datasets, and sources whose terms permit the intended collection and use.
- Respect applicable privacy, data-protection, marketing, copyright, robots/access rules, rate limits, and contractual restrictions. Obtain legal review for launch jurisdictions and use cases.
- Do not bypass authentication, paywalls, CAPTCHAs, technical access controls, or provider restrictions.
- Publicly visible business contact information is not blanket permission to send marketing email. Product 04 must enforce an approved lawful basis/consent policy, suppression lists, unsubscribe handling, and relevant jurisdictional rules before sending.
- Do not collect sensitive personal data or infer sensitive traits.
- Keep source references and timestamps so customers can inspect where a lead came from.
- Provide abuse controls, quotas, rate limits, audit events, and a customer-facing explanation when collection is restricted.

## 9. Acceptance criteria (future implementation gate)

- A customer can create a tenant-scoped search job and retrieve it after leaving/reopening the page.
- Search criteria and exclusions are persisted and visible.
- Every discovered record has provenance; unsupported/inferred email addresses are never presented as verified.
- Deduplication is deterministic and tested across repeated job runs.
- Email verification statuses accurately communicate their evidence and limitations.
- Fit score and data quality are separately visible and explainable.
- Job stage progress is durable and delivered to the frontend using the shared job-progress contract.
- Retry, cancellation, partial completion, and worker-crash recovery are tested.
- Tenant isolation, role permissions, plan limits, audit logging, deletion/retention, and export are tested.
- Outreach handoff cannot bypass Product 04 eligibility, suppression, approval, or compliance gates.
- Live provider/source tests are separately reported from mocked tests.

## 10. Out of scope until separately approved

- Unrestricted scraping of arbitrary websites.
- Guessing personal email addresses and presenting them as discovered contacts.
- Guaranteed mailbox existence or guaranteed delivery.
- Automatic cold-email sending without explicit customer configuration, eligibility checks, and required approvals.
- Building separate AI agents/models for every pipeline stage by default.
