from app.api.v1.media_assets import _signature


def test_media_signature_is_stable_and_asset_specific(monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "secret_key", "test-secret")
    first = _signature("asset-a", 2_000_000_000)
    assert first == _signature("asset-a", 2_000_000_000)
    assert first != _signature("asset-b", 2_000_000_000)
    assert first != _signature("asset-a", 2_000_000_001)


def test_video_signature_validation_rejects_mime_spoofing(tmp_path):
    from app.api.v1.media_assets import _valid_video_signature

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00")
    assert _valid_video_signature(video, "video/mp4")
    assert not _valid_video_signature(video, "video/webm")

    video.write_bytes(bytes.fromhex("1A45DFA3") + b"webm-data")
    assert _valid_video_signature(video, "video/webm")
    assert not _valid_video_signature(video, "video/quicktime")


def test_tiktok_media_upload_rejects_files_smaller_than_chunk_minimum(client, tmp_path, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "media_storage_dir", str(tmp_path))
    response = client.post("/api/v1/auth/register", json={
        "email": "small-video@example.com", "password": "StrongPass123!",
        "full_name": "Small Video", "organization_name": "Video Workspace",
    })
    assert response.status_code == 201
    body = response.json()
    organization_id = body["organization"]["id"]
    headers = {
        "Authorization": f"Bearer {body['access_token']}",
        "Content-Type": "video/mp4",
        "X-File-Name": "too-small.mp4",
    }
    prefix = b"\x00\x00\x00\x18ftypisom"
    video = prefix + b"x" * (5 * 1024 * 1024 - 1 - len(prefix))
    uploaded = client.post(
        f"/api/v1/organizations/{organization_id}/media-assets", headers=headers, content=video,
    )
    assert uploaded.status_code == 413
    assert "at least 5 MiB" in uploaded.json()["detail"]
    assert list(tmp_path.iterdir()) == []


def test_signature_check_rejects_non_ascii_input_without_raising(monkeypatch):
    """hmac.compare_digest raises TypeError for non-ASCII str; that must not become a 500."""
    from app.api.v1.media_assets import _signature, _signature_matches
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "secret_key", "test-secret")
    good = _signature("asset-a", 2_000_000_000)
    assert _signature_matches(good, "asset-a", 2_000_000_000)
    assert not _signature_matches(good, "asset-b", 2_000_000_000)
    assert not _signature_matches("\u00e9" * 64, "asset-a", 2_000_000_000)
    assert not _signature_matches("", "asset-a", 2_000_000_000)


def test_uploaded_filename_is_decoded_and_sanitised():
    from app.api.v1.media_assets import _clean_filename

    assert _clean_filename("My%20Launch%20Video.mp4") == "My Launch Video.mp4"
    assert _clean_filename("caf%C3%A9.mp4") == "caf\u00e9.mp4"
    assert _clean_filename("..%2F..%2Fetc%2Fpasswd") == "passwd"
    assert _clean_filename("C%3A%5Cclips%5Cdemo.mp4") == "demo.mp4"
    assert _clean_filename("bad%0D%0Aname.mp4") == "badname.mp4"
    assert _clean_filename("100% done.mp4") == "100% done.mp4"
    assert _clean_filename("") == "video"
    assert _clean_filename(None) == "video"
    assert len(_clean_filename("a" * 400 + ".mp4")) == 255
