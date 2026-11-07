"""Password hashing and signed access-token helpers."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

# Argon2id is the default variant of argon2-cffi's PasswordHasher (OWASP-recommended).
_password_hasher = PasswordHasher()

# Legacy scheme: kept only so accounts created before the Argon2id switch can still log in.
_PASSWORD_SCHEME = "pbkdf2_sha256"
_TOKEN_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with Argon2id (random salt and parameters are embedded in the result)."""
    return _password_hasher.hash(password)


def _verify_legacy_pbkdf2(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_text, salt_hex, expected_hex = password_hash.split("$", 3)
        if scheme != _PASSWORD_SCHEME:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id hash, or a legacy PBKDF2 hash."""
    if password_hash.startswith("$argon2"):
        try:
            return _password_hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
    return _verify_legacy_pbkdf2(password, password_hash)


_DUMMY_PASSWORD_HASH = _password_hasher.hash("timing-equalizer-not-a-real-password")


def spend_password_check_time(password: str) -> None:
    """Do a real Argon2 verification whose result is ignored.

    Called when a login names an unknown email, so that case takes about as long as a wrong
    password for a real account and response time does not reveal which emails are registered.
    """
    verify_password(password, _DUMMY_PASSWORD_HASH)


def password_needs_rehash(password_hash: str) -> bool:
    """True for legacy hashes or Argon2 hashes made with outdated parameters."""
    if not password_hash.startswith("$argon2"):
        return True
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(user_id: UUID, token_version: int = 0) -> str:
    """Issue a signed access token.

    `jti` identifies this one token so logout can revoke it. `ver` is the user's session version;
    bumping it on the user record (password change/reset, "sign out everywhere") invalidates every
    token issued before the bump.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
        "jti": uuid4().hex,
        "ver": token_version,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_TOKEN_ALGORITHM)


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: UUID
    jti: str | None  # None for tokens issued before revocation support existed
    version: int
    expires_at: datetime


def decode_access_claims(token: str) -> AccessTokenClaims | None:
    """Verify signature, expiry and type; return the claims or None if the token is unusable."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_TOKEN_ALGORITHM])
        if payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
            return None
        jti = payload.get("jti")
        version = payload.get("ver", 0)
        exp = payload.get("exp")
        if (jti is not None and not isinstance(jti, str)) or not isinstance(version, int) or isinstance(version, bool):
            return None
        if not isinstance(exp, (int, float)):
            return None
        return AccessTokenClaims(
            user_id=UUID(payload["sub"]),
            jti=jti,
            version=version,
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        )
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None


def decode_access_token(token: str) -> UUID | None:
    """Backward-compatible helper: the user id from a valid token, ignoring revocation state."""
    claims = decode_access_claims(token)
    return claims.user_id if claims else None


def generate_reset_token() -> str:
    """A URL-safe one-time secret (256 bits). Only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """SHA-256 is appropriate here because the token is high-entropy random, not a password."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_login_code(phone_e164: str, code: str) -> str:
    """Keyed hash of a short numeric sign-in code.

    A 6-digit code is only 1,000,000 possibilities, so a plain hash could be reversed instantly if the table
    leaked. Keying it with SECRET_KEY (and binding it to the phone number) prevents that.
    """
    key = get_settings().secret_key.encode("utf-8")
    return hmac.new(key, f"{phone_e164}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()
