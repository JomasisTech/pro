"""Encryption helpers for third-party OAuth tokens."""
from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().social_token_encryption_key
    if not key:
        raise RuntimeError("Social token encryption is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise RuntimeError("SOCIAL_TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from None


def encrypt_token(token: str) -> bytes:
    return _fernet().encrypt(token.encode("utf-8"))


def decrypt_token(token: bytes) -> str:
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        raise RuntimeError("Stored social credential could not be decrypted") from None
