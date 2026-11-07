from pathlib import Path

import httpx
import pytest

from app.modules.posting.tiktok_upload import (
    TikTokUploadError,
    upload_video_file,
    validate_upload_url,
)


def test_upload_video_file_sends_sequential_ranges(tmp_path: Path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"abcdefghij")
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.headers["content-range"], request.content))
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transferred = upload_video_file(
            "https://open-upload.tiktokapis.com/video/?upload_id=1&upload_token=x",
            video,
            "video/mp4",
            chunk_size=4,
            client=client,
        )

    assert transferred == 10
    assert requests == [
        ("bytes 0-3/10", b"abcd"),
        ("bytes 4-7/10", b"efgh"),
        ("bytes 8-9/10", b"ij"),
    ]


@pytest.mark.parametrize("url", [
    "http://open-upload.tiktokapis.com/video/?token=x",
    "https://evil.example/video/?token=x",
    "https://user:pass@open-upload.tiktokapis.com/video/?token=x",
    "https://open-upload.tiktokapis.com/video/",
])
def test_upload_url_rejects_untrusted_destinations(url: str):
    with pytest.raises(TikTokUploadError):
        validate_upload_url(url)


def test_upload_rejects_empty_file_and_unsupported_content_type(tmp_path: Path):
    video = tmp_path / "empty.mp4"
    video.write_bytes(b"")
    url = "https://open-upload.tiktokapis.com/video/?upload_id=1"
    with pytest.raises(TikTokUploadError, match="empty"):
        upload_video_file(url, video, "video/mp4")
    video.write_bytes(b"video")
    with pytest.raises(TikTokUploadError, match="content type"):
        upload_video_file(url, video, "application/octet-stream")
