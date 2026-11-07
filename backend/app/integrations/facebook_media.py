"""Read recent published posts from a Facebook Page via the Graph API."""
from datetime import datetime, timezone
from typing import Any

import httpx

GRAPH_API_VERSION = "v26.0"
FACEBOOK_POSTS_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
FACEBOOK_POST_FIELDS = "id,message,permalink_url,created_time"


class FacebookMediaError(RuntimeError):
    """Raised when Facebook does not return a usable Page post collection."""


def fetch_recent_facebook_page_posts(page_id: str, page_access_token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch up to 20 recent Page posts; never include access tokens in raised errors."""
    if not page_id or not page_access_token:
        raise FacebookMediaError("Facebook Page identity or access token is missing")
    safe_limit = max(1, min(int(limit), 20))
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            response = client.get(
                f"{FACEBOOK_POSTS_URL}/{page_id}/posts",
                params={"fields": FACEBOOK_POST_FIELDS, "limit": safe_limit},
                headers={"Authorization": f"Bearer {page_access_token}"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        raise FacebookMediaError("Facebook could not return recent Page posts") from None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise FacebookMediaError("Facebook returned an unexpected Page posts response")
    posts: list[dict[str, Any]] = []
    for item in data[:safe_limit]:
        if not isinstance(item, dict):
            continue
        source_id = item.get("id")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 200:
            continue
        published_at = None
        created_time = item.get("created_time")
        if isinstance(created_time, str) and created_time:
            try:
                published_at = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        message, permalink = item.get("message"), item.get("permalink_url")
        posts.append({"source_post_id": source_id, "post_text": message[:10000] if isinstance(message, str) else "",
                      "permalink": permalink[:1000] if isinstance(permalink, str) else None,
                      "published_at": published_at, "media_type": "post"})
    return posts
