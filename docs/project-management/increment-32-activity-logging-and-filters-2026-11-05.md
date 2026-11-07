# Increment 32 — activity logging and filter UI (2026-11-05)

## Added
- **Logged events:** `auth.registered` (new account), `auth.login` (email/password, Google, WhatsApp) and `content.caption_generated` / `content.video_script_generated` (AI generation; summary holds a short snippet of the topic). Role changes, member removal, plan/subscription changes were already logged.
- **Sign-ins are workspace-scoped:** the log belongs to a workspace, so a sign-in is written to every workspace the user belongs to (max 10). Failed sign-ins are NOT logged (no verified user or workspace to attach them to). A logging failure never blocks sign-in (`record_user_event` in `app/modules/audit/activity.py`).
- **Activity page filter:** dropdown of categories mapped to the existing `action_prefix` API parameter; "Load more" respects the active filter.

## Tests
`tests/test_activity.py` (registration, sign-in, multi-workspace sign-in, failed sign-in, prefix filter), `tests/test_content.py` (generation logged). Two existing assertions were adjusted for the new `auth.*` entries (`test_activity.py` helper/pagination, `test_business_products_and_confirmation.py`).

## Verification
Python compile passed; TypeScript syntax check passed. NOT run: pytest, lint, typecheck, build, browser.

## Still open
Retention/export/text search for the log; password-change and sign-out-everywhere events; organisation-level audit of failed sign-ins.
