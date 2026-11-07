# Instructions for AI coding assistants

Before making any change in this repository:

1. Read `docs/project-management/master-development-prompt.md`.
2. Read `docs/project-management/project-status.md`.
3. Read relevant entries in `development-rules.md`, `known-issues.md`, and `decisions-log.md`.
4. Inspect existing code before editing it. Do not assume prior work is tested.
5. Work in small increments: normally one file at a time, or a tightly coupled file plus its test when required.
6. Explain the intended change briefly, make the smallest useful change, and run relevant tests if an execution environment is available.
7. Do not claim tests passed unless they were actually run; report exact limitations if they could not be run.
8. Update project-management documentation when work or status changes.
9. Never commit secrets, `.env` files, or real tokens.
10. Do not implement future products prematurely. Follow the current stage in `project-status.md`.
11. Preserve the modular-monolith architecture and other decisions unless a change is justified and recorded.
12. The project owner is using a mobile phone and expects the assistant to prepare code and repository-ready files rather than ask them to write code manually.

13. Follow the required strategy in the master prompt: stabilize the foundation, establish the frontend shell early, then implement one feature at a time as a tested backend/frontend vertical slice.
14. Do not complete the whole backend roadmap before beginning frontend work, and do not build all layers/features in uncontrolled parallel.
15. For each slice, document the API contract, test backend behavior, connect the frontend, and report the exact verification performed and remaining gaps.

16. Read `docs/full-project-blueprint.md` to understand the long-term destination, but use `docs/project-management/project-status.md` to determine current scope. The target tree is not a command to create every future module now.
17. Unless the owner explicitly changes scope, work only on the current foundation and Product 01 Social Media Automation. Treat Products 02–07 as future roadmap.

## Visual design references
Before making frontend or styling changes, read `docs/design-reference/README.md` and inspect the reference images in that folder. Treat the desktop dark screenshot as the primary visual reference, the mobile screenshot as a responsive-layout reference, and the desktop light screenshot as the light-theme reference. Keep brand colors centralized in shared design tokens; do not scatter raw colors across components. The screenshots are guidance, not templates to copy page-for-page.

18. Every endpoint that creates, edits, deletes, or approves organization-owned data must write an activity-log entry with `record_activity` before committing (see `docs/activity-log.md`). Plan-limited actions must use the central catalog in `backend/app/core/plans.py` (see `docs/plans-and-limits.md`).


19. For future long-running customer workflows, read `docs/architecture/background-job-progress.md`. The backend must persist authoritative job/stage state and the frontend must display backend-confirmed progress, counters, waiting/approval states, and safe errors. Do not implement a progress animation that is disconnected from real job state.
20. Product 02 lead generation, Product 04 AI outreach, and Product 06 data collection requirements are documented under `docs/products/`. These documents preserve future scope; they do not override the active Product 01 scope in `project-status.md`.
