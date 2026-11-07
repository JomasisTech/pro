"""Server-side transfer of a stored video to a TikTok Direct Post upload session."""
from pathlib import Path
from urllib.parse import urlparse

import httpx

ALLOWED_UPLOAD_HOST = "open-upload.tiktokapis.com"
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024


class TikTokUploadError(RuntimeError):
    """Raised when a TikTok upload session or media transfer is invalid."""


def validate_upload_url(upload_url: str) -> None:
    parsed = urlparse(upload_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != ALLOWED_UPLOAD_HOST
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.query
    ):
        raise TikTokUploadError("TikTok returned an invalid upload session URL")


def upload_video_file(
    upload_url: str,
    file_path: str | Path,
    content_type: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    client: httpx.Client | None = None,
) -> int:
    """PUT a local media asset in sequential chunks and return bytes transferred.

    A fresh upload URL should be initialized immediately before calling this
    function; TikTok documents that these URLs expire after one hour.
    """
    validate_upload_url(upload_url)
    if content_type not in {"video/mp4", "video/quicktime", "video/webm"}:
        raise TikTokUploadError("Unsupported TikTok video content type")
    if chunk_size <= 0:
        raise TikTokUploadError("Chunk size must be positive")
    path = Path(file_path)
    total_size = path.stat().st_size
    if total_size <= 0:
        raise TikTokUploadError("Video file is empty")

    owns_client = client is None
    session = client or httpx.Client(timeout=180.0, follow_redirects=False)
    transferred = 0
    try:
        with path.open("rb") as source:
            while transferred < total_size:
                chunk = source.read(chunk_size)
                if not chunk:
                    raise TikTokUploadError("Video file ended before its recorded size")
                start = transferred
                end = start + len(chunk) - 1
                response = session.put(
                    upload_url,
                    content=chunk,
                    headers={
                        "Content-Type": content_type,
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {start}-{end}/{total_size}",
                    },
                )
                response.raise_for_status()
                transferred += len(chunk)
    except httpx.HTTPError as exc:
        raise TikTokUploadError("TikTok video transfer failed") from exc
    finally:
        if owns_client:
            session.close()
    return transferred
