"""Encryption key rotation support."""
import logging
from typing import Optional
from app.shared.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)

class KeyRotator:
    """Support multiple encryption keys for rotation.
    
    New data is encrypted with the primary key.
    Old data encrypted with previous keys can still be decrypted.
    """
    
    def __init__(self, primary_key: str, previous_keys: list[str] | None = None):
        self.primary_key = primary_key
        self.previous_keys = previous_keys or []
        self._key_index = 0
    
    def encrypt(self, data: bytes | str) -> str:
        """Encrypt with the primary key."""
        plaintext = data.decode() if isinstance(data, bytes) else data
        encrypted = encrypt(plaintext)
        # Prepend key index for identification
        return f"v{self._key_index}:{encrypted}"
    
    def decrypt(self, token: str) -> bytes:
        """Decrypt with any available key."""
        if ":" not in token:
            # Legacy format (no version prefix)
            result = decrypt(token)
            return result.encode() if isinstance(result, str) else result
        
        version_str, encrypted = token.split(":", 1)
        key_index = int(version_str.lstrip("v"))
        
        if key_index == self._key_index:
            result = decrypt(encrypted)
            return result.encode() if isinstance(result, str) else result
        
        # Try previous keys
        prev_idx = key_index - 1
        if 0 <= prev_idx < len(self.previous_keys):
            # Use the appropriate previous key
            from cryptography.fernet import Fernet
            fernet = Fernet(self.previous_keys[prev_idx].encode())
            return fernet.decrypt(encrypted.encode())
        
        raise ValueError(f"No key available for version {key_index}")
    
    def get_all_keys(self) -> list[str]:
        """Get all available keys."""
        return [self.primary_key] + self.previous_keys
    
    def rotate(self, new_key: str) -> None:
        """Rotate to a new key. Old key becomes previous."""
        self.previous_keys.insert(0, self.primary_key)
        self.primary_key = new_key
        self._key_index += 1
        logger.info(f"Encryption key rotated to version {self._key_index}")
