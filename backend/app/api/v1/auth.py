"""Registration, login, and current-user endpoints."""

import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.demo import is_demo_platform_admin
from app.modules.audit.activity import record_user_event
from app.core.database import get_db
from app.core.network import resolve_client_ip
from app.core.rate_limit import FailedAttemptLimiter, build_limiter
from app.core.slug import build_organization_slug
from app.core.security import (
    AccessTokenClaims,
    create_access_token,
    decode_access_claims,
    generate_reset_token,
    hash_login_code,
    hash_password,
    hash_reset_token,
    password_needs_rehash,
    spend_password_check_time,
    verify_password,
)
from app.integrations.email import send_email
from app.integrations.whatsapp import send_login_code
from app.models import PlatformAdminRole, AuthIdentity, EmailVerificationToken, Membership, Organization, PasswordResetToken, PhoneLoginCode, RevokedToken, User, PlatformLoginEvent
from app.schemas import (
    AuthProvidersResponse,
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OrganizationResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SetCredentialsRequest,
    TokenRequest,
    UpdateAccountRequest,
    UserResponse,
    WhatsAppCodeRequest,
    WhatsAppVerifyRequest,
    TotpVerifyRequest,
)

log = logging.getLogger(__name__)


def _record_platform_login_event(db: Session, user: User, method: str, request: Request) -> None:
    """Best-effort sign-in telemetry; never let analytics break authentication."""
    try:
        db.add(PlatformLoginEvent(
            user_id=user.id,
            method=method[:32],
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
            ip_address=resolve_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else "unknown", _settings.trusted_proxy_count),
            success=True,
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.warning("Could not record %s sign-in telemetry for user %s", method, user.id, exc_info=True)
router = APIRouter(prefix="/auth", tags=["authentication"])
bearer_scheme = HTTPBearer(auto_error=False)

_settings = get_settings()
login_limiter = build_limiter(_settings.login_max_failed_attempts, _settings.login_lockout_seconds, redis_url=_settings.redis_url, prefix="bizpilot:login:account")
# Optional second limiter per client address (all emails) to slow password spraying.
login_ip_limiter: FailedAttemptLimiter | None = (
    build_limiter(_settings.login_ip_max_failed_attempts, _settings.login_lockout_seconds, redis_url=_settings.redis_url, prefix="bizpilot:login:ip")
    if _settings.login_ip_max_failed_attempts > 0
    else None
)
# Password reset and password change are throttled in memory like the login limiter (see known-issues.md).
reset_email_limiter = build_limiter(_settings.password_reset_max_requests, _settings.password_reset_window_seconds, redis_url=_settings.redis_url, prefix="bizpilot:reset:email")
reset_ip_limiter = build_limiter(_settings.password_reset_max_requests * 10, _settings.password_reset_window_seconds, redis_url=_settings.redis_url, prefix="bizpilot:reset:ip")
verification_email_limiter = build_limiter(_settings.email_verification_max_requests, _settings.email_verification_window_seconds, redis_url=_settings.redis_url, prefix="bizpilot:verify:email")
verification_ip_limiter = build_limiter(_settings.email_verification_max_requests * 10, _settings.email_verification_window_seconds, redis_url=_settings.redis_url, prefix="bizpilot:verify:ip")
password_change_limiter = build_limiter(_settings.login_max_failed_attempts, _settings.login_lockout_seconds, redis_url=_settings.redis_url, prefix="bizpilot:password:change")

# WhatsApp sign-in codes: per client address (the per-number limits live in the database).
whatsapp_request_ip_limiter = build_limiter(_settings.whatsapp_login_max_codes_per_hour * 10, 3600, redis_url=_settings.redis_url, prefix="bizpilot:whatsapp:request")
whatsapp_verify_ip_limiter = build_limiter(_settings.whatsapp_login_max_verify_attempts * 10, 3600, redis_url=_settings.redis_url, prefix="bizpilot:whatsapp:verify")

_RESET_REQUEST_MESSAGE = "If an account exists for that email, a password reset link has been sent."
_VERIFY_REQUEST_MESSAGE = "If the account exists and needs verification, a verification link has been sent."


def _aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC so comparisons work on every database."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_configured_platform_admin(user: User) -> bool:
    allowed = {item.strip().casefold() for item in _settings.platform_admin_emails.split(",") if item.strip()}
    return bool(user.email and user.email_verified_at is not None and user.email.casefold() in allowed)


def _is_platform_admin_user(user: User, db: Session) -> bool:
    return is_demo_platform_admin(user, _settings) or _is_configured_platform_admin(user) or db.scalar(select(PlatformAdminRole.id).where(PlatformAdminRole.user_id == user.id)) is not None


def _auth_response(user: User, membership: Membership, db: Session, *, mfa_verified: bool = False) -> AuthResponse:
    if _is_platform_admin_user(user, db) and not is_demo_platform_admin(user, _settings) and user.totp_enabled and (not user.totp_secret or not mfa_verified):
        raise HTTPException(status_code=403, detail="Platform administrators must enable MFA and sign in with their password and authenticator code.")
    organization = membership.organization
    return AuthResponse(
        access_token=create_access_token(user.id, user.token_version),
        user=UserResponse.model_validate(user),
        organization=OrganizationResponse(
            id=organization.id, name=organization.name, slug=organization.slug, role=membership.role
        ),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> AuthResponse:
    """Create a user, their first organization, and an owner membership."""
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=payload.email, password_hash=hash_password(payload.password), full_name=payload.full_name)
    organization = Organization(name=payload.organization_name, slug=build_organization_slug(payload.organization_name))
    membership = Membership(user=user, organization=organization, role="owner")
    db.add_all([user, organization, membership])
    try:
        db.commit()
        db.refresh(user)
        db.refresh(membership)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create account with the supplied details") from None
    if user.email and user.email_verified_at is None:
        token = _issue_email_verification_token(db, user)
        background_tasks.add_task(_send_verification_email, user.email, token)
    record_user_event(db, user, "auth.registered", f"{user.full_name} created the account with email and password", only_first_membership=True)
    return _auth_response(user, membership, db)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """Authenticate an active user and issue a short-lived access token."""
    client_ip = resolve_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else "unknown",
        _settings.trusted_proxy_count,
    )
    limiter_key = f"{payload.email}|{client_ip}"
    wait_seconds = login_limiter.retry_after(limiter_key)
    if login_ip_limiter is not None:
        wait_seconds = max(wait_seconds, login_ip_limiter.retry_after(client_ip))
    if wait_seconds:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(wait_seconds)},
        )
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        spend_password_check_time(payload.password)  # keep response time similar to a wrong password
    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            try:
                db.add(PlatformLoginEvent(user_id=user.id, method="password", user_agent=(request.headers.get("user-agent") or "")[:300] or None, ip_address=client_ip, success=False)); db.commit()
            except SQLAlchemyError:
                db.rollback()
        login_limiter.record_failure(limiter_key)
        if login_ip_limiter is not None:
            login_ip_limiter.record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # Only the per-account counter is cleared. The per-address counter is not, otherwise an attacker
    # could reset it by logging in to their own account between guesses.
    login_limiter.reset(limiter_key)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")
    if _settings.email_verification_required and user.email and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Please verify your email address before signing in")
    if _is_platform_admin_user(user, db) and not is_demo_platform_admin(user, _settings) and user.totp_enabled:
        if not payload.totp_code or not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(payload.totp_code, valid_window=1):
            try:
                db.add(PlatformLoginEvent(user_id=user.id, method="password_mfa", user_agent=(request.headers.get("user-agent") or "")[:300] or None, ip_address=client_ip, success=False)); db.commit()
            except SQLAlchemyError:
                db.rollback()
            login_limiter.record_failure(limiter_key)
            if login_ip_limiter is not None:
                login_ip_limiter.record_failure(client_ip)
            raise HTTPException(status_code=401, detail="A valid authenticator code is required for platform administrator sign-in")
    if password_needs_rehash(user.password_hash):
        # Upgrade legacy PBKDF2 (or outdated-parameter) hashes to Argon2id after a successful login.
        user.password_hash = hash_password(payload.password)
        db.commit()
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at).limit(1)
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="No organization is associated with this account")
    record_user_event(db, user, "auth.login", f"{user.full_name} signed in with email and password")
    _record_platform_login_event(db, user, "password", request)
    return _auth_response(user, membership, db, mfa_verified=bool(_is_platform_admin_user(user, db) and user.totp_enabled and payload.totp_code and user.totp_secret and pyotp.TOTP(user.totp_secret).verify(payload.totp_code, valid_window=1)))


def _authenticate(credentials: HTTPAuthorizationCredentials | None, db: Session) -> tuple[User, AccessTokenClaims]:
    unauthorized = {"WWW-Authenticate": "Bearer"}
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required", headers=unauthorized)
    claims = decode_access_claims(credentials.credentials)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers=unauthorized)
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive account", headers=unauthorized)
    # A password change/reset or "sign out everywhere" bumps token_version and ends older sessions.
    if claims.version != user.token_version:
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers=unauthorized)
    if _settings.email_verification_required and user.email and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Please verify your email address to access this account")
    if claims.jti is not None and db.get(RevokedToken, claims.jti) is not None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers=unauthorized)
    return user, claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve a valid, unrevoked bearer token to an active user."""
    return _authenticate(credentials, db)[0]


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> tuple[User, AccessTokenClaims]:
    """Like get_current_user, but also returns the token claims (used by logout)."""
    return _authenticate(credentials, db)


@router.post("/2fa/setup")
def start_totp_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    """Create a pending authenticator secret. It is not enabled until verified."""
    secret = pyotp.random_base32()
    current_user.totp_pending_secret = secret
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=current_user.email or str(current_user.id), issuer_name="BizPilotPro")
    return {"secret": secret, "otpauth_uri": uri, "message": "Scan this QR code with your authenticator app, then verify a code."}


@router.post("/2fa/verify")
def verify_totp_setup(payload: TotpVerifyRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    """Activate TOTP only after a valid code from the authenticator app."""
    secret = current_user.totp_pending_secret
    if not secret or not pyotp.TOTP(secret).verify(payload.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="The authenticator code is invalid. Try again.")
    current_user.totp_secret = secret
    current_user.totp_pending_secret = None
    current_user.totp_enabled = True
    # Revoke all existing sessions so future administrator access must complete MFA at sign-in.
    current_user.token_version += 1
    db.commit()
    return {"message": "Two-factor authentication is now enabled. Sign in again with your authenticator code."}


@router.post("/2fa/cancel")
def cancel_totp_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    current_user.totp_pending_secret = None
    db.commit()
    return {"message": "Authenticator setup cancelled."}


@router.get("/2fa/status")
def totp_status(current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    return {"enabled": bool(current_user.totp_enabled)}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the profile for the authenticated user."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateAccountRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserResponse:
    """Update the signed-in user's display name. Email changes need verification and are not supported yet."""
    current_user.full_name = payload.full_name
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


def _first_membership(db: Session, user: User) -> Membership:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at).limit(1)
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="No organization is associated with this account")
    return membership


@router.post("/logout", response_model=MessageResponse)
def logout(
    session: tuple[User, AccessTokenClaims] = Depends(get_current_session), db: Session = Depends(get_db)
) -> MessageResponse:
    """End this session: the presented access token stops working immediately."""
    user, claims = session
    if claims.jti is None:
        # Token predates per-token ids and cannot be listed individually; end all older sessions instead.
        user.token_version += 1
    else:
        db.add(RevokedToken(jti=claims.jti, user_id=user.id, expires_at=claims.expires_at))
    # Tokens that have expired anyway no longer need a denylist row.
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))
    db.commit()
    return MessageResponse(message="Signed out")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    """Sign out everywhere: every access token issued so far, on every device, stops working."""
    user.token_version += 1
    db.commit()
    return MessageResponse(message="Signed out on all devices")


def _send_password_changed_email(user_email: str | None) -> None:
    if not user_email:
        return
    send_email(
        _settings,
        user_email,
        "Your AutoBizPro password was changed",
        "The password for your AutoBizPro account was just changed and all sessions were signed out.\n\n"
        "If this was you, no action is needed. If it was not you, reset your password immediately "
        "using the 'Forgot password' link on the sign-in page.",
    )


@router.post("/change-password", response_model=AuthResponse)
def change_password(
    payload: ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Change the password of the signed-in user and end all of their other sessions."""
    if not user.has_password:
        raise HTTPException(
            status_code=400,
            detail="This account signs in with Google or WhatsApp and has no password to change.",
        )
    limiter_key = str(user.id)
    wait_seconds = password_change_limiter.retry_after(limiter_key)
    if wait_seconds:
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(wait_seconds)},
        )
    if not verify_password(payload.current_password, user.password_hash):
        password_change_limiter.record_failure(limiter_key)
        raise HTTPException(status_code=400, detail="Your current password is incorrect")
    password_change_limiter.reset(limiter_key)
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Choose a new password that is different from your current one")
    membership = _first_membership(db, user)
    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    user.token_version += 1
    # Any reset link requested earlier must not work after the password has changed.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    db.refresh(user)
    background_tasks.add_task(_send_password_changed_email, user.email)
    return _auth_response(user, membership, db)


@router.post("/set-credentials", response_model=AuthResponse)
def set_credentials(
    payload: SetCredentialsRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Add a password (and an email, if the account has none) to a WhatsApp or Google account.

    Accounts that already have a password use change-password instead. A newly added email is unverified
    until the person opens the link we send. All other sessions end, like a password change.
    """
    if user.has_password:
        raise HTTPException(status_code=400, detail="This account already has a password. Use change password instead.")
    limiter_key = f"credentials:{user.id}"
    wait_seconds = verification_email_limiter.retry_after(limiter_key)
    if wait_seconds:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a while and try again.",
            headers={"Retry-After": str(wait_seconds)},
        )
    verification_email_limiter.record_failure(limiter_key)

    new_email: str | None = None
    if user.email is None:
        if not payload.email:
            raise HTTPException(status_code=400, detail="Enter the email address you want to sign in with")
        if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
            raise HTTPException(status_code=409, detail="That email address can't be used for this account")
        new_email = payload.email
    elif payload.email and payload.email != user.email:
        raise HTTPException(status_code=400, detail="The email address on this account can't be changed here")

    membership = _first_membership(db, user)
    now = datetime.now(timezone.utc)
    if new_email:
        user.email = new_email
        user.email_verified_at = None
    user.password_hash = hash_password(payload.password)
    user.has_password = True
    user.password_changed_at = now
    user.token_version += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That email address can't be used for this account") from None
    db.refresh(user)
    if new_email:
        token = _issue_email_verification_token(db, user)
        background_tasks.add_task(_send_verification_email, new_email, token)
    record_user_event(
        db, user, "auth.credentials_added",
        f"{user.full_name} added {'an email and ' if new_email else ''}a password to the account",
    )
    return _auth_response(user, membership, db)


def _send_reset_email(user_email: str, token: str) -> None:
    base_url = _settings.frontend_base_url.rstrip("/")
    if _settings.app_env.lower() == "production" and not base_url.startswith("https://"):
        log.error("FRONTEND_BASE_URL must be an HTTPS URL in production; password reset email was not sent")
        return
    # The token is in the URL fragment so it is not sent to servers, logs, or referrer headers.
    link = f"{base_url}/reset-password#token={token}"
    send_email(
        _settings,
        user_email,
        "Reset your AutoBizPro password",
        f"We received a request to reset your AutoBizPro password.\n\nOpen this link to choose a new one "
        f"(it expires in {_settings.password_reset_ttl_minutes} minutes and can be used once):\n\n{link}\n\n"
        "If you did not request this, you can ignore this email; your password has not changed.",
    )


@router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Email a one-time reset link. The answer is identical whether or not the account exists."""
    client_ip = resolve_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else "unknown",
        _settings.trusted_proxy_count,
    )
    wait_seconds = max(reset_email_limiter.retry_after(payload.email), reset_ip_limiter.retry_after(client_ip))
    if wait_seconds:
        raise HTTPException(
            status_code=429,
            detail="Too many reset requests. Please wait before trying again.",
            headers={"Retry-After": str(wait_seconds)},
        )
    # Every request counts, whether or not the account exists, so the limit reveals nothing.
    reset_email_limiter.record_failure(payload.email)
    reset_ip_limiter.record_failure(client_ip)

    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.is_active:
        now = datetime.now(timezone.utc)
        # Only the newest link should work.
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        token = generate_reset_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_reset_token(token),
                expires_at=now + timedelta(minutes=_settings.password_reset_ttl_minutes),
            )
        )
        db.commit()
        background_tasks.add_task(_send_reset_email, user.email, token)
    return MessageResponse(message=_RESET_REQUEST_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> MessageResponse:
    """Set a new password using a valid reset token, and sign out every existing session."""
    invalid = HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    now = datetime.now(timezone.utc)
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(payload.token)))
    if record is None or record.used_at is not None or _aware(record.expires_at) <= now:
        raise invalid
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise invalid
    # Atomically claim the token so two simultaneous requests cannot both succeed.
    claimed = db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == record.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise invalid
    user.password_hash = hash_password(payload.new_password)
    user.has_password = True  # a Google-created account that resets its password can now use it too
    user.password_changed_at = now
    user.token_version += 1
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    background_tasks.add_task(_send_password_changed_email, user.email)
    return MessageResponse(message="Your password has been updated. Please sign in with your new password.")



def _issue_email_verification_token(db: Session, user: User) -> str:
    now = datetime.now(timezone.utc)
    db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = generate_reset_token()
    db.add(EmailVerificationToken(
        user_id=user.id, token_hash=hash_reset_token(token),
        expires_at=now + timedelta(minutes=_settings.email_verification_ttl_minutes),
    ))
    db.commit()
    return token


def _send_verification_email(user_email: str, token: str) -> None:
    base_url = _settings.frontend_base_url.rstrip("/")
    if _settings.app_env.lower() == "production" and not base_url.startswith("https://"):
        log.error("FRONTEND_BASE_URL must be HTTPS in production; verification email was not sent")
        return
    link = f"{base_url}/verify-email#token={token}"
    send_email(
        _settings, user_email, "Verify your AutoBizPro email address",
        "Please confirm that you own this email address by opening the link below. "
        f"The link expires in {_settings.email_verification_ttl_minutes} minutes and can be used once:\n\n{link}\n\n"
        "If you did not create this account, you can ignore this message.",
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: TokenRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Consume a single-use verification token and mark the account email as verified."""
    now = datetime.now(timezone.utc)
    record = db.scalar(select(EmailVerificationToken).where(
        EmailVerificationToken.token_hash == hash_reset_token(payload.token)
    ))
    invalid = HTTPException(status_code=400, detail="This verification link is invalid or has expired. Request a new one.")
    if record is None or record.used_at is not None or _aware(record.expires_at) <= now:
        raise invalid
    user = db.get(User, record.user_id)
    if user is None or not user.is_active or not user.email:
        raise invalid
    claimed = db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.id == record.id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise invalid
    user.email_verified_at = now
    db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.commit()
    return MessageResponse(message="Your email address has been verified. You can now sign in.")


@router.post("/resend-verification", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    payload: ForgotPasswordRequest, request: Request, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Send a replacement verification link without disclosing whether an email has an account."""
    client_ip = resolve_client_ip(
        request.headers.get("x-forwarded-for"), request.client.host if request.client else "unknown",
        _settings.trusted_proxy_count,
    )
    wait = max(verification_email_limiter.retry_after(payload.email), verification_ip_limiter.retry_after(client_ip))
    if wait:
        raise HTTPException(status_code=429, detail="Too many verification requests. Please wait before trying again.", headers={"Retry-After": str(wait)})
    verification_email_limiter.record_failure(payload.email)
    verification_ip_limiter.record_failure(client_ip)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.is_active and user.email_verified_at is None:
        token = _issue_email_verification_token(db, user)
        background_tasks.add_task(_send_verification_email, user.email, token)
    return MessageResponse(message=_VERIFY_REQUEST_MESSAGE)


# --------------------------------------------------------------------------------------
# Social sign-in: Google (OpenID Connect) and WhatsApp (one-time code)
# --------------------------------------------------------------------------------------

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
# One shared client so Google's signing keys are cached instead of downloaded on every sign-in.
_google_jwks_client = PyJWKClient(_GOOGLE_JWKS_URL)
_GOOGLE_COOKIE_NAMES = ("google_oauth_state", "google_oauth_nonce")


def _same_secret(a: str, b: str) -> bool:
    """Constant-time comparison that also accepts non-ASCII text (hmac.compare_digest rejects it for str)."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _google_cookie_path() -> str:
    return f"{_settings.api_v1_prefix}/auth/google/callback"


def _frontend_login_url(error: str | None = None) -> str:
    """The sign-in page on the same origin as the configured frontend return URL."""
    parts = urlsplit(_settings.google_login_frontend_return_url)
    url = f"{parts.scheme}://{parts.netloc}/login"
    return f"{url}?{urlencode({'social_error': error})}" if error else url


def _clear_google_cookies(response: RedirectResponse) -> RedirectResponse:
    for name in _GOOGLE_COOKIE_NAMES:
        response.delete_cookie(name, path=_google_cookie_path())
    return response


def _google_failure(reason: str = "google") -> RedirectResponse:
    """Send the browser back to the login page with a short, non-revealing error code."""
    return _clear_google_cookies(RedirectResponse(_frontend_login_url(reason), status_code=302))


def _new_social_user(*, email: str | None, full_name: str, workspace_name: str, email_verified: bool) -> tuple[User, Membership]:
    """A user plus a first workspace they own. Nobody knows the password, so password sign-in is impossible."""
    user = User(
        email=email,
        full_name=full_name[:160],
        password_hash=hash_password(secrets.token_urlsafe(48)),
        has_password=False,
        email_verified_at=datetime.now(timezone.utc) if email_verified else None,
    )
    organization = Organization(name=workspace_name[:160], slug=build_organization_slug(workspace_name))
    membership = Membership(user=user, organization=organization, role="owner")
    return user, membership


@router.get("/providers", response_model=AuthProvidersResponse)
def auth_providers() -> AuthProvidersResponse:
    """Tell the sign-in pages which social options work here, so they never show a button that errors."""
    return AuthProvidersResponse(
        google=_settings.google_login_configured,
        # In development an unconfigured WhatsApp sender logs the code to the server console instead.
        whatsapp=_settings.whatsapp_login_configured or _settings.app_env.lower() == "development",
    )


@router.get("/demo")
def demo_info() -> dict[str, object]:
    """Lets the login page show the demo account. Reveals nothing unless DEMO_MODE is on (never in production)."""
    if not _settings.demo_mode:
        return {"enabled": False}
    return {"enabled": True, "email": _settings.demo_email, "password": _settings.demo_password}


@router.post("/demo-admin", response_model=AuthResponse)
def demo_admin_login(request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """Issue an owner session for the separate seeded administrator demo identity; unavailable outside DEMO_MODE."""
    if not _settings.demo_mode:
        raise HTTPException(status_code=404, detail="Demo administrator access is not available")
    user = db.scalar(select(User).where(User.email == _settings.demo_admin_email.strip().lower()))
    if user is None or not is_demo_platform_admin(user, _settings):
        raise HTTPException(status_code=503, detail="The separate demo administrator account is not ready. Restart the demo server and try again.")
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at).limit(1)
    )
    if membership is None:
        raise HTTPException(status_code=503, detail="The demo administrator workspace is not ready")
    record_user_event(db, user, "auth.demo_admin_login", "Signed in to the isolated platform administrator demo")
    _record_platform_login_event(db, user, "demo_admin", request)
    return _auth_response(user, membership, db)


@router.get("/google")
def google_login() -> RedirectResponse:
    """Start Google OpenID Connect login (scopes: openid, email, profile only)."""
    if not _settings.google_login_configured:
        # The browser navigates here directly, so answer with a page-friendly redirect, not raw JSON.
        return RedirectResponse(_frontend_login_url("google_unavailable"), status_code=302)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    params = {
        "client_id": _settings.google_login_client_id,
        "redirect_uri": _settings.google_login_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{_GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}", status_code=302)
    for name, value in (("google_oauth_state", state), ("google_oauth_nonce", nonce)):
        response.set_cookie(
            name, value, max_age=600, httponly=True,
            secure=_settings.app_env.lower() == "production", samesite="lax", path=_google_cookie_path(),
        )
    return response


def _fetch_google_claims(code: str, expected_nonce: str) -> dict | None:
    """Exchange the authorization code and return verified ID-token claims, or None if anything is wrong."""
    with httpx.Client(timeout=12.0) as client:
        token_response = client.post(_GOOGLE_TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": _settings.google_login_client_id,
            "client_secret": _settings.google_login_client_secret,
            "redirect_uri": _settings.google_login_redirect_uri,
            "grant_type": "authorization_code",
        })
        token_response.raise_for_status()
        id_token = token_response.json().get("id_token")
    if not id_token:
        return None
    signing_key = _google_jwks_client.get_signing_key_from_jwt(id_token).key
    claims = jwt.decode(
        id_token, signing_key, algorithms=["RS256"], audience=_settings.google_login_client_id,
        issuer=_GOOGLE_ISSUERS, options={"require": ["exp", "iat", "sub", "email"]},
    )
    if claims.get("email_verified") not in (True, "true") or not claims.get("sub") or not claims.get("email"):
        return None
    if not _same_secret(str(claims.get("nonce", "")), expected_nonce):
        return None
    return claims


@router.get("/google/callback")
def google_login_callback(
    request: Request, code: str | None = None, state: str | None = None,
    error: str | None = None, db: Session = Depends(get_db),
) -> RedirectResponse:
    """Validate Google's signed ID token, resolve or create the user, and hand back a short-lived API token."""
    expected_state = request.cookies.get("google_oauth_state")
    expected_nonce = request.cookies.get("google_oauth_nonce")
    if (
        error or not code or not state or not expected_state or not expected_nonce
        or not _settings.google_login_configured
        or not _same_secret(state, expected_state)
    ):
        return _google_failure()
    try:
        claims = _fetch_google_claims(code, expected_nonce)
        if claims is None:
            return _google_failure()
        subject = str(claims["sub"])
        email = str(claims["email"]).strip().lower()
        identity = db.scalar(select(AuthIdentity).where(
            AuthIdentity.provider == "google", AuthIdentity.provider_subject == subject
        ))
        if identity is not None:
            user = db.get(User, identity.user_id)
        else:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                full_name = str(claims.get("name") or email.split("@")[0])
                user, membership = _new_social_user(
                    email=email, full_name=full_name, workspace_name=f"{full_name}'s Workspace", email_verified=True
                )
                db.add_all([user, membership.organization, membership])
                db.flush()
            elif user.email_verified_at is None:
                # This email was registered with a password, but we never confirmed that whoever registered it
                # owns the address. Linking Google here would hand that person's password to the real owner's
                # account ("pre-hijacking"). Refuse; the password owner can still sign in normally.
                return _google_failure("email_exists")
            db.add(AuthIdentity(user_id=user.id, provider="google", provider_subject=subject))
            db.commit()
            db.refresh(user)
        if user is None or not user.is_active:
            return _google_failure()
        membership = db.scalar(
            select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at).limit(1)
        )
        if membership is None:
            return _google_failure()
        record_user_event(db, user, "auth.login", f"{user.full_name} signed in with Google")
        _record_platform_login_event(db, user, "google", request)
        result = _auth_response(user, membership, db)
        success = RedirectResponse(f"{_settings.google_login_frontend_return_url.rstrip('/')}#access_token={result.access_token}", status_code=302)
        return _clear_google_cookies(success)
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, IntegrityError):
        db.rollback()
        log.exception("Google sign-in failed")
        return _google_failure()


def _client_ip(request: Request) -> str:
    return resolve_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else "unknown",
        _settings.trusted_proxy_count,
    )


def _send_whatsapp_code(phone: str, code: str) -> None:
    send_login_code(_settings, phone, code)


@router.post("/whatsapp/request-code", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def whatsapp_request_code(
    payload: WhatsAppCodeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Send a 6-digit sign-in code to a WhatsApp number. The answer does not reveal whether the number has an account."""
    if not auth_providers().whatsapp:
        raise HTTPException(status_code=503, detail="WhatsApp sign-in is not available right now")
    client_ip = _client_ip(request)
    wait_seconds = whatsapp_request_ip_limiter.retry_after(client_ip)
    if wait_seconds:
        raise HTTPException(
            status_code=429, detail="Too many code requests. Please wait before trying again.",
            headers={"Retry-After": str(wait_seconds)},
        )
    whatsapp_request_ip_limiter.record_failure(client_ip)

    now = datetime.now(timezone.utc)
    recent = db.scalars(
        select(PhoneLoginCode)
        .where(PhoneLoginCode.phone_e164 == payload.phone, PhoneLoginCode.created_at >= now - timedelta(hours=1))
        .order_by(PhoneLoginCode.created_at.desc())
    ).all()
    if recent:
        since_last = (now - _aware(recent[0].created_at)).total_seconds()
        if since_last < _settings.whatsapp_login_resend_seconds:
            wait = int(_settings.whatsapp_login_resend_seconds - since_last) + 1
            raise HTTPException(
                status_code=429, detail=f"A code was just sent. You can ask for another in {wait} seconds.",
                headers={"Retry-After": str(wait)},
            )
    if len(recent) >= _settings.whatsapp_login_max_codes_per_hour:
        raise HTTPException(
            status_code=429, detail="Too many codes requested for this number. Please try again later.",
            headers={"Retry-After": "3600"},
        )

    # Only the newest code may work.
    db.execute(
        update(PhoneLoginCode)
        .where(PhoneLoginCode.phone_e164 == payload.phone, PhoneLoginCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(PhoneLoginCode(
        phone_e164=payload.phone,
        code_hash=hash_login_code(payload.phone, code),
        expires_at=now + timedelta(minutes=_settings.whatsapp_login_code_ttl_minutes),
    ))
    db.commit()
    background_tasks.add_task(_send_whatsapp_code, payload.phone, code)
    return MessageResponse(message="If that number can receive WhatsApp messages, a sign-in code is on its way.")


@router.post("/whatsapp/verify", response_model=AuthResponse)
def whatsapp_verify(payload: WhatsAppVerifyRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """Check the code; sign in the account for this number, creating it (and a first workspace) if new."""
    invalid = HTTPException(status_code=400, detail="That code is incorrect or has expired. Request a new one.")
    client_ip = _client_ip(request)
    wait_seconds = whatsapp_verify_ip_limiter.retry_after(client_ip)
    if wait_seconds:
        raise HTTPException(
            status_code=429, detail="Too many incorrect codes. Please wait before trying again.",
            headers={"Retry-After": str(wait_seconds)},
        )
    now = datetime.now(timezone.utc)
    record = db.scalar(
        select(PhoneLoginCode)
        .where(PhoneLoginCode.phone_e164 == payload.phone, PhoneLoginCode.consumed_at.is_(None))
        .order_by(PhoneLoginCode.created_at.desc())
        .limit(1)
    )
    if record is None or _aware(record.expires_at) <= now:
        whatsapp_verify_ip_limiter.record_failure(client_ip)
        raise invalid
    # Count this guess atomically *before* checking it, so parallel guesses cannot exceed the limit.
    counted = db.execute(
        update(PhoneLoginCode)
        .where(PhoneLoginCode.id == record.id, PhoneLoginCode.attempts < _settings.whatsapp_login_max_verify_attempts)
        .values(attempts=PhoneLoginCode.attempts + 1)
    )
    db.commit()
    if counted.rowcount != 1:
        whatsapp_verify_ip_limiter.record_failure(client_ip)
        raise invalid
    if not hmac.compare_digest(record.code_hash, hash_login_code(payload.phone, payload.code)):
        whatsapp_verify_ip_limiter.record_failure(client_ip)
        raise invalid
    # Atomically claim the code so it can be used once even if two requests race.
    claimed = db.execute(
        update(PhoneLoginCode)
        .where(PhoneLoginCode.id == record.id, PhoneLoginCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise invalid

    identity = db.scalar(select(AuthIdentity).where(
        AuthIdentity.provider == "whatsapp", AuthIdentity.provider_subject == payload.phone
    ))
    if identity is not None:
        user = db.get(User, identity.user_id)
        db.commit()
    else:
        # "WhatsApp user" is a placeholder the interface recognises and asks the person to replace.
        user, membership = _new_social_user(
            email=None,
            full_name=payload.full_name or "WhatsApp user",
            workspace_name=f"{payload.full_name}'s Workspace" if payload.full_name else "My Workspace",
            email_verified=False,
        )
        db.add_all([user, membership.organization, membership])
        db.flush()
        db.add(AuthIdentity(user_id=user.id, provider="whatsapp", provider_subject=payload.phone))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise invalid from None
        db.refresh(user)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")
    record_user_event(db, user, "auth.login", f"{user.full_name} signed in with WhatsApp")
    _record_platform_login_event(db, user, "whatsapp", request)
    return _auth_response(user, _first_membership(db, user), db)
