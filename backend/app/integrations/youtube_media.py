"""Read recent videos from the authenticated YouTube channel via YouTube Data API."""
from datetime import datetime, timezone
from typing import Any

import httpx

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeMediaError(RuntimeError):
    """Raised when YouTube cannot return a usable video collection."""


def _get_json(client: httpx.Client, path: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
    response = client.get(
        f"{YOUTUBE_API_BASE}/{path}", params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise YouTubeMediaError("YouTube returned an unexpected response")
    return payload


def fetch_recent_youtube_videos(access_token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch up to 20 recent uploads from the channel authorized by the token."""
    if not access_token:
        raise YouTubeMediaError("YouTube access token is missing")
    safe_limit = max(1, min(int(limit), 20))
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            channels = _get_json(client, "channels", access_token, {"part": "contentDetails", "mine": "true"})
            items = channels.get("items")
            if not isinstance(items, list) or not items or not isinstance(items[0], dict):
                raise YouTubeMediaError("No YouTube channel is available for this account")
            content = items[0].get("contentDetails") or {}
            related = content.get("relatedPlaylists") or {}
            uploads_id = related.get("uploads")
            if not isinstance(uploads_id, str) or not uploads_id:
                raise YouTubeMediaError("YouTube did not provide an uploads playlist")
            playlist = _get_json(client, "playlistItems", access_token, {
                "part": "snippet,contentDetails", "playlistId": uploads_id, "maxResults": safe_limit,
            })
    except YouTubeMediaError:
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise YouTubeMediaError("YouTube could not return recent channel videos") from None

    rows = playlist.get("items")
    if not isinstance(rows, list):
        raise YouTubeMediaError("YouTube returned an unexpected uploads playlist")
    posts: list[dict[str, Any]] = []
    for item in rows[:safe_limit]:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet") or {}
        details = item.get("contentDetails") or {}
        resource = snippet.get("resourceId") or {}
        video_id = details.get("videoId") or resource.get("videoId")
        if not isinstance(video_id, str) or not video_id or len(video_id) > 200:
            continue
        title = snippet.get("title")
        description = snippet.get("description")
        text = "\n\n".join(value for value in (title, description) if isinstance(value, str) and value)
        published_at = None
        published = snippet.get("publishedAt")
        if isinstance(published, str) and published:
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        posts.append({
            "source_post_id": video_id, "post_text": text[:10000],
            "permalink": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": published_at, "media_type": "video",
        })
    return posts
