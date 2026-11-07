"""Read recent media from an Instagram professional account using Instagram Login."""
from datetime import datetime, timezone
from typing import Any

import httpx


INSTAGRAM_MEDIA_URL = "https://graph.instagram.com/me/media"
INSTAGRAM_MEDIA_FIELDS = "id,caption,media_type,permalink,timestamp"


class InstagramMediaError(RuntimeError):
    """Raised when Meta does not return a usable media collection."""


def fetch_recent_instagram_media(access_token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch at most ``limit`` recent media items; never expose provider tokens in errors."""
    if not access_token:
        raise InstagramMediaError("Instagram access token is missing")
    safe_limit = max(1, min(int(limit), 20))
    try:
        response = httpx.get(
            INSTAGRAM_MEDIA_URL,
            params={"fields": INSTAGRAM_MEDIA_FIELDS, "limit": safe_limit},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        raise InstagramMediaError("Instagram could not return recent media") from None

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise InstagramMediaError("Instagram returned an unexpected media response")

    posts: list[dict[str, Any]] = []
    for item in data[:safe_limit]:
        if not isinstance(item, dict):
            continue
        source_id = item.get("id")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 200:
            continue
        published_at = None
        timestamp = item.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            try:
                published_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except ValueError:
                published_at = None
        caption = item.get("caption")
        permalink = item.get("permalink")
        posts.append({
            "source_post_id": source_id,
            "post_text": caption[:10000] if isinstance(caption, str) else "",
            "permalink": permalink[:1000] if isinstance(permalink, str) else None,
            "published_at": published_at,
            "media_type": item.get("media_type") if isinstance(item.get("media_type"), str) else None,
        })
    return posts
