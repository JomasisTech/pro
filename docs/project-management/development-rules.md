# Development Rules

1. Build one product at a time; Product 1 is Social Media Automation.
2. Keep the backend a modular monolith unless a documented decision justifies otherwise.
3. Build only the modules needed for the current stage.
4. Keep content creation separate from posting/publishing workflows.
5. Keep organization-owned data scoped and authorized on the backend when multi-tenancy is introduced.
6. Never commit `.env` files, credentials, tokens, or production secrets.
7. Use SQLAlchemy for database access and Alembic for schema migrations.
8. Add tests for important features and failure paths.
9. Do not claim a feature is complete without test evidence.
10. Update project status, completed work, known issues, and decisions after each stage.
11. Prefer official social platform APIs and OAuth; never collect social account passwords.
12. Explain important implementation and security decisions in beginner-friendly language.

13. Use a **foundation-first, then vertical-slice** workflow: verify the basic backend/runtime and database foundation, establish the frontend shell early, then deliver each capability through backend + frontend + integration tests.
14. Do not finish the entire backend roadmap before starting the frontend; do not build all frontend and backend features in uncontrolled parallel either.
15. For each feature, define the API contract, implement backend logic and tests, implement the corresponding UI, connect both, and verify the complete workflow before moving on.
16. Keep security foundations (authentication, authorization, tenant isolation, secrets handling) ahead of features that depend on them; enforce access controls on the backend.
17. Clearly distinguish unit tests, mocked/SQLite tests, real PostgreSQL verification, external-provider verification, and deployment checks. Never treat one as proof of another.
18. Update `project-status.md` and `decisions-log.md` when the development sequence or a major implementation decision changes.

19. Long-running backend workflows must expose durable, tenant-authorized progress to the frontend. Persist job and stage state before publishing progress; use replayable events or a snapshot plus bounded polling fallback. The UI must reflect backend-confirmed state, not simulated progress. See `docs/architecture/background-job-progress.md`.
20. For lead discovery, use approved/licensed sources and retain provenance. Do not bypass access controls or infer email addresses and label them as discovered/verified. Public business contact details do not automatically authorize marketing email. Follow Product 02, Product 04, and Product 06 requirements.
21. Keep AI responsibilities separate from deterministic controls: use AI for language understanding, classification, qualification explanations, and writing; use ordinary code/provider services for normalization, deduplication, syntax checks, authorization, quotas, suppression, idempotency, and delivery state. Multiple AI models are optional and require demonstrated benefit.
