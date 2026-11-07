# Product 01 — Hybrid Brand Intelligence Requirements

**Product:** BizPilot Pro — Social Media Automation  
**Status:** Agreed product requirement; partially implemented. Durable provider sync jobs and the manual-sync dashboard exist for supported providers. Full reviewable analysis, conflict resolution, data lifecycle/deletion, and live provider verification remain subject to the checklist below and the current project status.  
**Applies to:** Onboarding, business profiles, social account connections, AI content generation, and future content automation.

## 1. Purpose

Build a useful understanding of each customer's business and communication style by combining information the customer provides with evidence from social media accounts they explicitly connect. This context should make generated content and other social automation more relevant and consistent with the customer's brand.

## 2. Core product decision

**Keep business/industry/niche onboarding. Add social content analysis as a complementary feature. Do not replace onboarding with AI inference.**

The user's declared industry, niche, business description, products/services, target audience, and goals are the starting business facts. Social posts can enrich the understanding of content themes and communication style, but must not silently redefine the business.

## 3. Information sources

### 3.1 User-provided profile (required)

Collect and maintain, as applicable:
- Business name.
- Industry and niche/subcategory.
- Business description.
- Products and services.
- Target audience.
- Location/markets served, where relevant.
- Business and marketing goals.
- Preferred brand voice, language, and content preferences.
- Brand assets such as logo and approved visual references.

This source remains sufficient to start using the product even when no social accounts are connected.

### 3.2 Connected social content (optional, permission-based)

After the user connects an account through the provider's official authorization flow and grants the necessary scopes, retrieve up to the 20 most recent posts available through that platform's official API. Twenty is a maximum target, not a guaranteed result. Respect pagination, API limits, account eligibility, scopes, review/approval requirements, and provider policies. If only 2, 5, or 0 posts are accessible, use that actual amount and do not imply that 20 were analysed.

Analyse only data the provider API and granted permissions make available. This may include captions/text, timestamps, post type, permitted media, hashtags, calls to action, and engagement/insight metrics where supported. Never ask for social account passwords, scrape content to bypass API restrictions, or claim unavailable metrics were collected.

## 4. What the AI should derive

From available content, identify useful, evidence-based observations such as:
- Recurring topics and content pillars.
- Writing style, tone, language, and sentence/format patterns.
- Common post formats (for example, text, image, carousel, or video) when available.
- Hashtag and call-to-action patterns.
- Repeated products, services, offers, and brand messages.
- Engagement patterns only when trustworthy platform metrics are available.
- Potential content opportunities and gaps, clearly labelled as recommendations rather than facts.

Do not infer sensitive personal attributes. Audience descriptions should be framed as tentative content/audience hypotheses unless supported by reliable, permissioned analytics.

## 5. Combining information and handling conflicts

- Maintain a unified business-level brand profile for consistent cross-platform identity.
- Allow platform-specific style observations where the same brand communicates differently on different networks.
- Preserve the origin of profile information: user-provided, provider-sourced, or AI-inferred.
- User-confirmed business facts take precedence over model inference.
- Do not silently change the declared industry, niche, products, or services based on posts.
- When sources conflict, retain the user's declared facts, surface the discrepancy in understandable language, and ask for confirmation when the conflict materially affects automation.
- Users must be able to review, edit, accept, or reject AI-generated observations.

## 6. Account maturity and evidence levels

| Situation | Required behavior |
|---|---|
| New business, no social account/posts | Use onboarding profile as the primary context; content generation remains available. |
| New account or only a few posts | Analyse available posts; label findings preliminary/low-evidence; rely primarily on onboarding. |
| Established account | Analyse up to 20 recent accessible posts and combine findings with onboarding. |
| Connected account over time | Refresh when new posts become available at a sensible frequency, subject to consent and provider limits. |
| No access, revoked permission, expired token, or provider outage | Preserve user-provided profile, explain that social analysis is unavailable/stale, and allow reconnection. |

Use clear qualitative evidence states such as **Initial**, **Developing**, and **Well-supported**. These states should reflect the quantity, recency, diversity, and quality of available evidence. Do not display a precise numeric confidence score unless it is later calibrated and validated.

## 7. User experience

1. During onboarding, the user enters business and niche information.
2. The user can continue without connecting a social account.
3. The user may connect one or more supported social accounts later or during onboarding.
4. Explain what data will be accessed and why before authorization/analysis.
5. Show the number of posts actually analysed and the date of analysis.
6. Present a reviewable brand profile, including what came from the user versus what the AI observed.
7. Let the user correct or dismiss inaccurate observations.
8. Let the user disconnect an account and request deletion of imported post data and derived analysis.

## 8. Refresh and data lifecycle

- Support an initial analysis and incremental refresh when new posts are detected.
- Avoid repeatedly processing unchanged posts; use provider identifiers and timestamps where permitted.
- Record last successful sync, analysis timestamp, accessible post count, provider/account status, and errors.
- Minimize retained post content; store only what is needed for the agreed product behavior.
- Define retention and deletion behavior before production release, including deletion of imported content and derived analysis when the user requests it or disconnects where appropriate.
- Encrypt provider access and refresh tokens at rest; never log tokens or secrets.

## 9. Platform integration requirements

Use official APIs and OAuth/authorization only. Implement platform adapters independently because platforms differ in supported account types, available post fields, media access, analytics, permissions, pagination, quotas, and app review. Verify current official documentation before committing to a platform capability. Never promise that every platform can provide the same 20-post dataset or insights.

## 10. Architecture guidance

Keep the existing FastAPI modular-monolith architecture. Expected responsibilities (create modules only when the active implementation slice needs them):
- Social integration adapters: OAuth, token refresh, account metadata, and provider API retrieval.
- Social sync service: pagination, incremental sync, provider limits, and sync status.
- Brand intelligence service: analysis of permitted content and reconciliation with the user profile.
- Business profile/brand profile persistence: user-confirmed facts, AI observations, source/provenance, evidence state, and timestamps.
- Content generation: consume the approved combined profile when building prompts.

Do not create microservices, empty modules, or an elaborate autonomous-agent framework for this feature. Implement one tested end-to-end vertical slice at a time.

## 11. Acceptance criteria

- [ ] Industry/niche and business-profile onboarding remain available and are not optionalized by social analysis.
- [ ] A user can complete onboarding and use AI content generation without connecting a social account.
- [ ] Connecting an eligible social account uses official authorization and clearly explains requested access.
- [ ] The system retrieves no more than 20 recent posts per account in the initial analysis, and accurately reports the number actually retrieved/analysed.
- [ ] Fewer than 20 posts, zero posts, unsupported account types, and API restrictions are handled without breaking onboarding or content generation.
- [ ] Analysis distinguishes user-provided facts from AI observations.
- [ ] AI observations do not silently overwrite the user's declared industry, niche, products, or services.
- [ ] Users can review, edit, accept, or reject AI-generated profile observations.
- [ ] Unified brand context and platform-specific style observations can coexist.
- [ ] Content generation uses the approved combined brand context.
- [ ] Refresh, stale/error states, token expiry/revocation, and disconnect/deletion behavior are handled.
- [ ] Tokens are encrypted and excluded from logs; imported data is minimized and tenant-isolated.
- [ ] Tests cover tenant isolation, permissions, empty/few-post accounts, provider failures, conflicting information, and profile updates.
- [ ] Documentation states which provider capabilities have actually been verified; no platform capability is assumed from another platform.

## 12. Implementation sequencing

This is an agreed Product 01 requirement, not authorization to skip foundation work. First complete the current foundation verification and secure social-account connection design. Then implement a provider connection and account-status vertical slice, followed by limited recent-post retrieval, analysis/review, and integration with AI content generation. Keep the user-provided business profile functional throughout.
