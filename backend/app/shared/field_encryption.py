"""Field-level encryption for sensitive data."""

import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class FieldEncryption:
    """Field-level encryption for sensitive data with per-field key derivation."""

    def __init__(self, master_key: str | bytes | None = None):
        """Initialize with master encryption key."""
        if master_key is None:
            master_key = settings.ENCRYPTION_KEY

        if isinstance(master_key, str):
            master_key = master_key.encode()

        self.master_key = master_key
        self._field_keys: dict[str, Fernet] = {}

    def _derive_key(self, field_name: str) -> Fernet:
        """Derive unique key per field for cryptographic isolation.
        
        Using PBKDF2HMAC ensures each field has a unique encryption key
        derived from the master key, preventing key reuse attacks.
        """
        if field_name not in self._field_keys:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=field_name.encode(),  # Field name as salt ensures unique key per field
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
            self._field_keys[field_name] = Fernet(key)
        return self._field_keys[field_name]

    def encrypt_field(self, field_name: str, value: Any | None) -> str | None:
        """Encrypt a single field value.
        
        Args:
            field_name: Name of the field (used for key derivation)
            value: Value to encrypt
            
        Returns:
            Encrypted value or None if input was None
        """
        if value is None or value == "":
            return value

        fernet = self._derive_key(field_name)
        value_str = value if isinstance(value, str) else str(value)
        return fernet.encrypt(value_str.encode()).decode()

    def decrypt_field(self, field_name: str, encrypted: str | None) -> str | None:
        """Decrypt a single field value.
        
        Args:
            field_name: Name of the field (used for key derivation)
            encrypted: Encrypted value
            
        Returns:
            Decrypted value or None if input was None
        """
        if encrypted is None or encrypted == "":
            return encrypted

        try:
            fernet = self._derive_key(field_name)
            return fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            # If decryption fails, return None or raise based on requirements
            return None

    def encrypt_dict(
        self,
        data: dict[str, Any],
        sensitive_fields: list[str]
    ) -> dict[str, Any]:
        """Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data to encrypt
            sensitive_fields: List of field names to encrypt
            
        Returns:
            Dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in sensitive_fields:
            if field in result and result[field] is not None:
                result[field] = self.encrypt_field(field, str(result[field]))
        return result

    def decrypt_dict(
        self,
        data: dict[str, Any],
        sensitive_fields: list[str]
    ) -> dict[str, Any]:
        """Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            sensitive_fields: List of field names to decrypt
            
        Returns:
            Dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in sensitive_fields:
            if field in result and result[field] is not None:
                decrypted = self.decrypt_field(field, result[field])
                if decrypted is not None:
                    result[field] = decrypted
        return result


# Global instance for convenience
_field_encryption: Optional[FieldEncryption] = None


def get_field_encryption() -> FieldEncryption:
    """Get or create global field encryption instance."""
    global _field_encryption
    if _field_encryption is None:
        _field_encryption = FieldEncryption()
        logger.info("FieldEncryption singleton initialized")
    return _field_encryption


# Common PII field definitions
PII_FIELDS = [
    "email",
    "phone",
    "phone_number",
    "address",
    "tax_id",
    "ssn",
    "passport_number",
    "date_of_birth",
]

SENSITIVE_FIELDS = [
    "api_key",
    "secret_key",
    "password",
    "token",
    "credential",
]
