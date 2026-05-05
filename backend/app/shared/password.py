"""Shared password hashing and verification utilities.

Extracted from auth.service to break the tight coupling between
user_management and auth modules. Both modules now import from
this shared utility instead of reaching into auth internals.
"""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${hashed}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a salted hash."""
    try:
        salt, stored_hash = hashed.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000).hex()
        return secrets.compare_digest(computed, stored_hash)
    except (ValueError, AttributeError):
        return False
