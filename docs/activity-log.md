# Activity log (audit trail)

Every important change inside an organization is recorded as an entry saying **who** did **what** and **when**.

`GET /api/v1/organizations/{organization_id}/activity?limit=50&offset=0` — **owners and admins only** (plain members get 403, other tenants 404). Newest first, `limit` 1–100. There is no route to edit or delete entries.

Entry fields: `action`, `entity_type`, `entity_id`, `summary`, `actor_user_id`, `actor_name`, `created_at`.

## What is logged now
| Action | When |
| --- | --- |
| `draft.created` / `draft.updated` / `draft.deleted` | A draft is saved, its text is edited (only if the text really changed), or it is deleted |
| `draft.approved` / `draft.rejected` / `draft.reopened` | An owner/admin changes a draft's status (only if it really changed) |
| `profile.created` / `profile.updated` | The business profile is saved |
| `organization.created` | A workspace is created from the dashboard |
| `business_product.created` / `business_product.updated` / `business_product.deleted` | A product or service is created, changed, or deleted |
| `business_product.primary_changed` | A previous primary offer loses its primary designation when another offer becomes primary |
| `social_account.connected` / `social_account.disconnected` | A provider OAuth callback successfully connects/reconnects an account, or an owner/admin disconnects it |
| `facebook_post.published` / `facebook_post.scheduled` | Facebook confirms an immediate post or a Meta-native scheduled post |
| `tiktok_publish_job.created` / `tiktok_publish_job.status_changed` | A TikTok Direct Post upload is initialized or its provider-confirmed status changes |
| `youtube_publish_job.created` / `youtube_publish_job.status_changed` | A YouTube resumable upload is initialized or its provider-confirmed status changes |

Not yet logged: account registration, logins, AI caption generations (counted in usage instead), and future features.

## Design rules (follow these for every new feature)
- Call `record_activity(db, membership, action, entity_type, entity_id, summary)` from `app/modules/audit/activity.py` in the endpoint, **before** `db.commit()`, so the change and its log entry are saved together or not at all.
- Log only changes that actually happened (not rejected or no-op requests).
- `actor_name` is stored as a snapshot, and `entity_id` has no foreign key, so entries stay readable after a user or the item is deleted.
- Summaries hold a short preview (about 60 characters) of user text, never secrets, tokens, or passwords.
- Never add an update/delete endpoint for the log. Retention and export are future decisions.

Frontend: `/activity` ("Activity Log" in the sidebar).


## Filtering

`GET .../activity` accepts optional `entity_type` (exact match, e.g. `draft`) and `action_prefix` (e.g. `draft.`; `%` and `_` are matched literally) in addition to `limit` and `offset`.
