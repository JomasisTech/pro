import hashlib

from app.core.security import hash_password, password_needs_rehash, verify_password


def _legacy_hash(password: str) -> str:
    salt = b"0123456789abcdef"
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${derived.hex()}"


def test_new_hashes_use_argon2id_and_verify():
    hashed = hash_password("a-long-unique-password")
    assert hashed.startswith("$argon2id$")
    assert verify_password("a-long-unique-password", hashed)
    assert not verify_password("wrong-password", hashed)
    assert not password_needs_rehash(hashed)


def test_hashes_are_salted():
    assert hash_password("same-password") != hash_password("same-password")


def test_legacy_pbkdf2_hash_still_verifies_and_is_flagged_for_upgrade():
    legacy = _legacy_hash("old-account-password")
    assert verify_password("old-account-password", legacy)
    assert not verify_password("nope", legacy)
    assert password_needs_rehash(legacy)


def test_garbage_hash_is_rejected():
    assert not verify_password("anything", "not-a-real-hash")
    assert not verify_password("anything", "$argon2id$broken")
