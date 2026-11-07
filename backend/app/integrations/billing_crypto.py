"""Encryption helpers for reusable payment authorizations."""
from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().billing_authorization_encryption_key
    if not key:
        raise RuntimeError("Billing authorization encryption is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise RuntimeError("BILLING_AUTHORIZATION_ENCRYPTION_KEY must be a valid Fernet key") from None


def encrypt_authorization_code(code: str) -> bytes:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("A valid authorization code is required")
    return _fernet().encrypt(code.encode("utf-8"))


def decrypt_authorization_code(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        raise RuntimeError("Stored billing authorization could not be decrypted") from None
