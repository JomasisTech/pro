# Organizations API (initial implementation)

Base prefix: `/api/v1/organizations`. All routes require `Authorization: Bearer <access_token>`.

| Method | Path | Who can call | Result |
| --- | --- | --- | --- |
| GET | `/organizations` | any signed-in user | Organizations the user belongs to, with the user's role |
| POST | `/organizations` | any signed-in user | Creates a workspace (`{"name": "..."}`, 2–160 characters, trimmed) and makes the caller its `owner`. Returns `201` with the organization. Returns `400` after 10 workspaces per user (`MAX_ORGANIZATIONS_PER_USER`, an interim guard until plans exist). Duplicate names are allowed; slugs get a random suffix. |
| GET | `/organizations/{organization_id}` | members of that organization | Organization details and the caller's role |
| GET | `/organizations/{organization_id}/members` | `owner` or `admin` of that organization | Members (user id, email, name, role) |

## Authorization rules

- Authorization is enforced in `backend/app/api/v1/organizations.py`, not in the frontend.
- `get_membership` loads the caller's membership for the organization in the URL. If there is none, the API returns **404**, not 403, so it never reveals whether another customer's organization exists.
- `require_roles("owner", "admin")` builds a dependency that returns **403** when a member's role is not allowed.
- Roles currently in use: `owner` (assigned at registration), `admin`, `member`. Invitations and role-changing endpoints do not exist yet.
- Every future organization-owned endpoint (business profiles, content, social accounts) must depend on one of these and filter its database queries by the membership's `organization_id`.


## Rename and delete a workspace (owner only)

- `PATCH /api/v1/organizations/{id}` with `{"name": "New name"}` renames the workspace (slug unchanged) and writes an `organization.renamed` activity entry.
- `DELETE /api/v1/organizations/{id}?confirm_name=<exact current name>` permanently deletes the workspace and all its data. Returns `204`. `400` if the name does not match or if it is the caller's only workspace; `403` for non-owners; `404` for non-members. Uploaded media files are removed from storage afterwards (best effort).
