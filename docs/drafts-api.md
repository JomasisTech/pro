# Drafts API and Content page

Base: `/api/v1/organizations/{organization_id}/drafts` (all routes need a bearer token and membership; non-members get 404).

| Method | Path | Who | Result |
| --- | --- | --- | --- |
| GET | `/drafts?status=draft\|approved\|rejected` | any member | Up to 100 drafts, newest first |
| POST | `/drafts` | any member | Saves `{content, topic?, content_type}` as a `draft` (201) |
| PATCH | `/drafts/{id}` | any member for `content`; `owner`/`admin` to change `status` | Updates and returns the draft |
| DELETE | `/drafts/{id}` | any member | 204 |

Rules: a draft is always looked up by id **and** the URL's organization, so another tenant's draft id returns 404. Editing the text of an approved/rejected draft puts it back to `draft` unless a status is sent in the same request. Saving a draft does not use plan quota; only generating a caption does (see `plans-and-limits.md`).

Frontend: `/content` (sidebar "Social Media") shows the plan usage line, a generate form, an editable result with "Save as draft", and the drafts list with edit, approve/reject (owners/admins), and delete. The generate button is disabled once the monthly caption limit is reached.


## Paging and delete permissions

`GET .../drafts` accepts `limit` (1-100, default 100) and `offset`, newest first. `DELETE` is allowed for the draft's author and for owners/admins; other members receive `403`.
