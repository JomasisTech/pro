# AI Content API (first slice: caption generation)

`POST /api/v1/organizations/{organization_id}/content/generate-caption` — any member of the organization.

Request: `{"topic": "2–300 chars", "content_type": "general | promotion | educational | product"}` (default `general`).
Response `200`: `{"caption": "...", "model": "..."}`. Nothing is saved yet (drafts come in the next slice).

| Status | Meaning |
| --- | --- |
| 401 / 404 | Not signed in / not a member of that organization |
| 409 | The organization has no business profile yet |
| 422 | Invalid topic or content type |
| 429 | Hourly limit reached (`AI_GENERATIONS_PER_HOUR`, default 20 per user); `Retry-After` is set |
| 502 | The AI provider failed (details are logged server-side only, not returned) |
| 503 | `OPENAI_API_KEY` is not configured |

## How it works
`app/integrations/ai_provider.py` holds the provider interface and the OpenAI HTTP client. `app/modules/content/prompts.py` turns the business profile (industry, description, audience, brand voice, language…) into the prompt. The route loads the profile through the same tenant check as every organization route. Profile text is treated as data in the system prompt, but prompt injection cannot be fully prevented; do not give the model tools or secrets.

Configuration: `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_REQUEST_TIMEOUT_SECONDS`, `AI_GENERATIONS_PER_HOUR` (see `backend/.env.example`).
