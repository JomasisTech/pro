"""Organization-owned private media upload and expiring signed delivery."""
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import quote, unquote
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.organizations import require_roles
from app.config import get_settings
from app.core.database import get_db
from app.models import Membership, MediaAsset
from app.modules.audit.activity import record_activity

router = APIRouter(tags=["Media assets"])
ALLOWED_TYPES = {"video/mp4", "video/quicktime", "video/webm"}


def _valid_video_signature(path: Path, content_type: str) -> bool:
    """Reject obvious MIME spoofing by checking the container's file signature."""
    with path.open("rb") as source:
        header = source.read(16)
    if content_type in {"video/mp4", "video/quicktime"}:
        # ISO Base Media File Format (MP4/MOV) identifies its file type at bytes 4..7.
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if content_type == "video/webm":
        # WebM is based on Matroska and starts with the EBML document signature.
        return header.startswith(bytes.fromhex("1A45DFA3"))
    return False


def _signature(asset_id: str, expires: int) -> str:
    settings = get_settings()
    return hmac.new(settings.secret_key.encode(), f"{asset_id}:{expires}".encode(), sha256).hexdigest()


def _signature_matches(provided: str, asset_id: str, expires: int) -> bool:
    """Constant-time check that also tolerates non-ASCII input.

    hmac.compare_digest raises TypeError for str arguments containing non-ASCII characters, which
    would turn a malformed (attacker-supplied) signature into a 500 instead of a 403.
    """
    return hmac.compare_digest(provided.encode("utf-8"), _signature(asset_id, expires).encode("ascii"))


def _clean_filename(raw: str | None) -> str:
    """Decode the percent-encoded X-File-Name header and keep only a safe display name.

    The browser sends encodeURIComponent(file.name) so that non-ASCII names survive HTTP headers.
    Path parts and control characters are dropped because the name is stored, shown in the activity
    log and sent back in a Content-Disposition header.
    """
    decoded = unquote(raw or "video")
    name = decoded.replace("\\", "/").split("/")[-1]
    name = "".join(character for character in name if character.isprintable()).strip()
    return name[:255] or "video"


@router.post("/organizations/{organization_id}/media-assets", status_code=201)
async def upload_media_asset(organization_id: UUID, request: Request,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    content_type = (request.headers.get("content-type") or "").split(";")[0].lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload an MP4, QuickTime, or WebM video")
    declared_size = request.headers.get("content-length")
    if declared_size and (not declared_size.isdigit() or int(declared_size) > settings.media_max_upload_bytes):
        raise HTTPException(status_code=413, detail="Video exceeds the configured upload limit")
    filename = _clean_filename(request.headers.get("x-file-name"))
    asset_id, storage_key = uuid4(), uuid4().hex
    root = Path(settings.media_storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / storage_key
    digest, size = sha256(), 0
    try:
        with destination.open("wb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > settings.media_max_upload_bytes:
                    raise HTTPException(status_code=413, detail="Video exceeds the configured upload limit")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded video is empty")
        if size < 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="TikTok scheduled videos must be at least 5 MiB for the configured chunked upload method")
        if not _valid_video_signature(destination, content_type):
            raise HTTPException(status_code=415, detail="The uploaded file does not match its declared video format")
        asset = MediaAsset(id=asset_id, organization_id=organization_id,
            uploaded_by_user_id=membership.user_id, storage_key=storage_key,
            original_filename=filename, content_type=content_type, size_bytes=size,
            sha256_hex=digest.hexdigest())
        db.add(asset)
        record_activity(db, membership, "media_asset.uploaded", "media_asset", asset.id,
                        f'Uploaded video asset "{filename[:80]}" ({size} bytes)')
        db.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        db.rollback()
        raise
    expires = int(datetime.now(timezone.utc).timestamp()) + settings.media_signed_url_ttl_seconds
    base = settings.media_public_base_url.rstrip("/")
    signed_url = f"{base}/api/v1/media-assets/{asset.id}/file?expires={expires}&signature={_signature(str(asset.id), expires)}" if base else None
    return {"id": str(asset.id), "filename": filename, "content_type": content_type,
            "size_bytes": size, "sha256": asset.sha256_hex, "status": "stored",
            "signed_url": signed_url, "signed_url_expires_at": expires if signed_url else None,
            "delivery_configured": bool(signed_url)}


@router.get("/media-assets/{asset_id}/file")
def deliver_media_asset(asset_id: UUID, expires: int, signature: str, db: Session = Depends(get_db)):
    now = int(datetime.now(timezone.utc).timestamp())
    if expires < now or expires > now + 7 * 86400 or not _signature_matches(signature, str(asset_id), expires):
        raise HTTPException(status_code=403, detail="Media URL is invalid or expired")
    asset = db.scalar(select(MediaAsset).where(MediaAsset.id == asset_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    path = Path(get_settings().media_storage_dir).resolve() / asset.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored media is unavailable")
    return FileResponse(path, media_type=asset.content_type, filename=asset.original_filename,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
