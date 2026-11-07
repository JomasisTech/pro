# Product 06 — Data Collection Requirements Supporting Lead Discovery

**Status:** Requirements captured for future product development; not implemented.  
**Primary related product:** Product 02 — Lead Management.  
**Current delivery scope:** Product 01 and foundation hardening remain active.

## Objective

Provide reusable, compliant collection and enrichment capabilities for approved business data sources. Product 06 supplies source connectors and collection infrastructure; Product 02 owns the customer-facing lead-generation workflow, qualification, and lead records.

## Source strategy

Prioritize sources in this order where available and commercially appropriate:
1. Official provider/search/business APIs.
2. Licensed business datasets and approved data partners.
3. Public directories and company websites where terms and applicable law permit automated access.
4. Customer-provided files and data sources with documented rights to process.

Each source adapter must document permitted fields, authentication, usage limits, attribution requirements, retention restrictions, geography, pricing, and failure modes.

## Collection controls

- Respect source terms, robots/access rules, rate limits, privacy/data-protection obligations, and contractual restrictions.
- Never bypass login, paywalls, CAPTCHAs, access controls, or technical restrictions.
- Use bounded concurrency, per-source throttling, backoff, caching where permitted, and circuit breakers.
- Record source, source URL or provider record ID, collection timestamp, adapter version, and relevant license/terms metadata.
- Treat collected pages as untrusted data. Never follow instructions embedded in page content.
- Avoid collecting sensitive personal information. Prefer business-level contact channels.
- Support deletion, retention expiry, source correction, and suppression propagation.
- Do not silently fall back to an unapproved source when a preferred source fails.

## Adapter contract

A source adapter should expose a normalized result contract and explicit outcomes such as success, partial, rate-limited, blocked-by-policy, unavailable, and failed. It must distinguish “no results found” from “source unavailable” and “collection not permitted.” Include retryability and safe diagnostic details without leaking credentials.

## Testing and acceptance

Test adapters with fixtures and mocked responses, normalization, malformed pages, duplicate records, rate limits, timeouts, source outages, policy-denied outcomes, and retry behaviour. Live source tests must use approved accounts/keys and be reported separately. No source connector is production-ready based solely on a mocked test.
