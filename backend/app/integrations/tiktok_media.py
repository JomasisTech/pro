"""Read recent public video metadata from an authorized TikTok account."""
from datetime import datetime, timezone
from typing import Any

import httpx

TIKTOK_VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
TIKTOK_VIDEO_FIELDS = "id,title,video_description,create_time,share_url,embed_link,cover_image_url,duration"


class TikTokMediaError(RuntimeError):
    """Raised when TikTok cannot return a usable video collection."""


def fetch_recent_tiktok_videos(access_token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch at most 20 recent videos using TikTok's video.list endpoint."""
    if not access_token:
        raise TikTokMediaError("TikTok access token is missing")
    safe_limit = max(1, min(int(limit), 20))
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            response = client.post(
                TIKTOK_VIDEO_LIST_URL,
                params={"fields": TIKTOK_VIDEO_FIELDS},
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"max_count": safe_limit},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        raise TikTokMediaError("TikTok could not return recent videos") from None

    if not isinstance(payload, dict):
        raise TikTokMediaError("TikTok returned an unexpected video response")
    error = payload.get("error")
    if isinstance(error, dict) and error.get("code") not in (None, "ok", "OK"):
        # Do not echo provider messages: they may contain request or account details.
        raise TikTokMediaError("TikTok rejected the video-list request")
    data = payload.get("data")
    videos = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(videos, list):
        raise TikTokMediaError("TikTok returned an unexpected video collection")

    posts: list[dict[str, Any]] = []
    for item in videos[:safe_limit]:
        if not isinstance(item, dict):
            continue
        source_id = item.get("id")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 200:
            continue
        published_at = None
        created = item.get("create_time")
        if isinstance(created, (int, float)) and not isinstance(created, bool):
            try:
                published_at = datetime.fromtimestamp(created, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                published_at = None
        description = item.get("video_description")
        title = item.get("title")
        text = description if isinstance(description, str) and description else title
        permalink = item.get("share_url") or item.get("embed_link")
        posts.append({
            "source_post_id": source_id,
            "post_text": text[:10000] if isinstance(text, str) else "",
            "permalink": permalink[:1000] if isinstance(permalink, str) else None,
            "published_at": published_at,
            "media_type": "video",
        })
    return posts
