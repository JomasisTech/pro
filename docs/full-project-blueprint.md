# Business Automation Platform — Full Project Blueprint

**Document type:** Long-term product and architecture blueprint  
**Status:** Target architecture; not a statement that these features already exist  
**Current delivery scope:** MVP foundation and Product 01 — Social Media Automation  
**Rule:** Build incrementally. Do not scaffold or implement the entire target tree at once.

## 1. Purpose

This document records the intended long-term shape of the Business Automation Platform so that future developers and AI coding assistants understand the destination while keeping current work focused.

The full tree supplied by the project owner is the **target structure**, not a requirement to create every file immediately. The current repository may be smaller because it represents the MVP and active implementation stage.

## 2. Delivery principles

1. **MVP first.** Finish and verify the current foundation and the first product, Social Media Automation, before expanding into the other products.
2. **Foundation first, then vertical slices.** Stabilize shared infrastructure, establish the frontend shell early, and then implement each user-facing capability end to end: API/data contract, backend logic, frontend experience, integration, and tests.
3. **Do not build everything at once.** Do not finish the entire backend roadmap before starting frontend work; do not build every layer and feature in uncontrolled parallel.
4. **Create files when needed.** The target tree is a planning map. Add a module, directory, or placeholder only when the active stage needs it or a documented dependency requires it.
5. **Preserve modular boundaries.** Keep the modular-monolith architecture. Each business module should own its routes, schemas, service logic, and models as appropriate. Shared concerns belong in `core/` or `integrations/`, not duplicated across modules.
6. **Security before dependent features.** Establish authentication, authorization, organization/tenant isolation, secret handling, and audit requirements before exposing protected data or external integrations.
7. **Official integrations only.** Social publishing and other third-party integrations must use official APIs and respect provider permissions, rate limits, and policies.
8. **Test evidence, not assumptions.** Distinguish unit tests, mocked/SQLite tests, real PostgreSQL checks, external-provider checks, and deployment checks. One is not proof of another.
9. **Update project records.** Keep `project-status.md`, `completed-work.md`, `known-issues.md`, and `decisions-log.md` current as appropriate.
10. **Do not claim completion from file presence.** A feature is complete only when its requirements, implementation, security, tests, UI/API integration, and relevant deployment checks have been verified.

## 3. Product roadmap

### Product 01 — Social Media Automation (current first product)
Intended scope includes:
- Business categories and business profile/onboarding.
- Social account connections and OAuth flows.
- Brand context and business analysis where appropriate.
- AI-assisted content generation, captions, templates, and content strategy.
- Content calendar and post approvals.
- Media handling and processing.
- Scheduling, publishing, platform capability checks, retries, and posting history.
- Supported platforms are subject to official API availability and approved permissions.

This is the first product to build and validate. Its detailed source of truth is:
`docs/products/product-01-social-media/`

### Product 02 — Lead Management
Future scope: lead records, lead workflows, qualification, and relevant integrations. Detailed requirements belong in:
`docs/products/product-02-lead-management/`

### Product 03 — Contact Management
Future scope: contact records, organization relationships, segmentation, and data lifecycle. Detailed requirements belong in:
`docs/products/product-03-contact-management/`

### Product 04 — Email Marketing
Future scope: email templates, campaigns, sending provider integration, opt-in/consent management, unsubscribe handling, delivery status, and compliant campaign workflows. Detailed requirements belong in:
`docs/products/product-04-email-marketing/`

### Product 05 — Analytics
Future scope: reporting, metrics, dashboards, and product-specific analytics. Detailed requirements belong in:
`docs/products/product-05-analytics/`

### Product 06 — Data Collection
Future scope: compliant data collection and source integrations. Collection must respect source terms, applicable law, privacy, robots/access controls, and rate limits; do not bypass access controls. Detailed requirements belong in:
`docs/products/product-06-data-collection/`

### Product 07 — Additional Automation
Future scope: additional workflow automation modules selected after the MVP and earlier products are validated. Detailed requirements belong in:
`docs/products/product-07-additional-automation/`

### Cross-cutting platform capabilities
The long-term platform may also include:
- Authentication and user management.
- Organizations and memberships, with tenant isolation.
- Notifications and audit/activity history.
- Billing and subscription management.
- AI provider abstraction.
- Email and storage provider abstraction.
- Background workers for long-running or scheduled tasks.
- Monitoring, deployment, backups, and operational documentation.

These are planned capabilities, not all current implementation commitments. Prioritize them according to dependencies and product validation.

## 4. Target repository structure

The project owner supplied the following intended destination tree. It is preserved here as a roadmap. Some files are future placeholders and should not be created until needed.

```text
business_automation_platform/
├── AGENTS.md
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── permissions.py
│   │   │   ├── dependencies.py
│   │   │   ├── exceptions.py
│   │   │   ├── logging.py
│   │   │   ├── pagination.py
│   │   │   └── constants.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       └── router.py
│   │   ├── modules/
│   │   │   ├── auth/ (router.py, service.py, models.py, schemas.py, utils.py)
│   │   │   ├── organizations/ (router.py, service.py, models.py, schemas.py)
│   │   │   ├── memberships/ (router.py, service.py, models.py, schemas.py)
│   │   │   ├── categories/ (router.py, service.py, repository.py, models.py, schemas.py, seed_data.py, README.md)
│   │   │   ├── profiles/ (router.py, service.py, models.py, schemas.py, business_analyzer.py, brand_context.py)
│   │   │   ├── social_accounts/ (router.py, service.py, models.py, schemas.py, oauth/facebook.py, instagram.py, x.py, tiktok.py)
│   │   │   ├── content/ (router.py, service.py, models.py, schemas.py, generator.py, strategy.py, templates.py, calendar.py, approvals.py, prompts/)
│   │   │   ├── posting/ (router.py, service.py, models.py, schemas.py, scheduler.py, tasks.py, publishers/)
│   │   │   ├── media/ (router.py, service.py, models.py, schemas.py, processing.py)
│   │   │   ├── leads/ (router.py, service.py, models.py, schemas.py)
│   │   │   ├── scraping/ (router.py, service.py, models.py, schemas.py, sources/base.py)
│   │   │   ├── contacts/ (router.py, service.py, models.py, schemas.py)
│   │   │   ├── email/ (router.py, service.py, models.py, schemas.py, templates.py, tasks.py)
│   │   │   ├── campaigns/ (router.py, service.py, models.py, schemas.py)
│   │   │   ├── analytics/ (router.py, service.py, models.py, schemas.py, reports.py)
│   │   │   ├── notifications/ (router.py, service.py, models.py, schemas.py)
│   │   │   └── billing/ (router.py, service.py, models.py, schemas.py, webhooks.py)
│   │   ├── integrations/
│   │   │   ├── ai/ (base.py, openai.py, factory.py)
│   │   │   ├── social/ (meta_client.py, x_client.py, tiktok_client.py)
│   │   │   ├── payments/ (base.py, paystack.py, flutterwave.py)
│   │   │   ├── email/ (base.py, resend.py, smtp.py)
│   │   │   └── storage/ (base.py, s3.py)
│   │   └── workers/
│   │       ├── __init__.py
│   │       ├── celery_app.py
│   │       ├── schedules.py
│   │       └── tasks/ (content_tasks.py, publishing_tasks.py, email_tasks.py, analytics_tasks.py)
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   ├── scripts/ (seed_categories.py, create_admin.py)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── public/ (images/, icons/, logo/)
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── globals.css
│   │   │   ├── (auth)/ (login/, register/, forgot-password/)
│   │   │   ├── onboarding/ (industry/, business-profile/, connect-accounts/)
│   │   │   └── dashboard/
│   │   │       ├── page.tsx
│   │   │       ├── social-accounts/
│   │   │       ├── content-calendar/
│   │   │       ├── posts/
│   │   │       ├── media/
│   │   │       ├── leads/
│   │   │       ├── contacts/
│   │   │       ├── email-campaigns/
│   │   │       ├── analytics/
│   │   │       ├── notifications/
│   │   │       ├── billing/
│   │   │       └── settings/
│   │   ├── components/ (ui/, layout/, dashboard/, forms/, shared/)
│   │   ├── features/ (auth/, onboarding/, categories/, profiles/, social-accounts/, content/, posting/, media/, leads/, contacts/, email/, campaigns/, analytics/, billing/)
│   │   ├── lib/ (api.ts, auth.ts, utils.ts, validations.ts)
│   │   ├── hooks/
│   │   ├── types/
│   │   └── store/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.ts
├── infrastructure/
│   ├── docker/docker-compose.yml
│   ├── deployment/
│   └── monitoring/
└── docs/
    ├── architecture.md
    ├── database-design.md
    ├── api-documentation.md
    ├── security.md
    ├── development-roadmap.md
    ├── integrations.md
    ├── project-management/
    └── products/
        ├── product-01-social-media/
        ├── product-02-lead-management/
        ├── product-03-contact-management/
        ├── product-04-email-marketing/
        ├── product-05-analytics/
        ├── product-06-data-collection/
        └── product-07-additional-automation/
```

The compact module entries above preserve the named file list from the supplied target structure. The authoritative per-product requirements and implementation details belong in the product documentation folders.

## 5. Scope control: current MVP versus target platform

When starting any task, an AI assistant must determine:
- What is currently implemented in the repository.
- What the current milestone says in `docs/project-management/project-status.md`.
- Whether the request belongs to the active MVP or a future product.
- What dependencies and security requirements must be satisfied first.

Unless the owner explicitly changes scope, work on the current foundation and Product 01 only. Do not begin Product 02–07 merely because they appear in this blueprint. Do not create empty modules just to make the repository resemble the target tree.

## 6. Definition of done

A product or feature is not complete merely because the expected folders exist. Completion requires:
- Requirements and acceptance criteria documented.
- Backend and frontend behavior implemented as applicable.
- API contracts and authorization enforced.
- Automated tests appropriate to the risk.
- Relevant integration and end-to-end tests.
- Real database/provider verification when claimed.
- Errors, loading states, and empty states handled.
- Security and privacy requirements checked.
- User-facing and developer documentation updated.
- Project status and known issues updated.
- Deployment and operational checks completed when the milestone requires them.

## 7. Instructions to future AI assistants

Before editing:
1. Read `AGENTS.md`.
2. Read `docs/project-management/master-development-prompt.md`.
3. Read this blueprint.
4. Read `docs/project-management/project-status.md`, `development-rules.md`, `known-issues.md`, and `decisions-log.md`.
5. Inspect the actual repository before assuming the target tree already exists.
6. Propose or continue the smallest useful, testable next step.
7. Make changes incrementally, run relevant checks, report exact results, and provide updated files/project archive when requested or when the archive is the delivery mechanism.

Never say that a planned module exists or is implemented unless the repository and tests support that statement.
