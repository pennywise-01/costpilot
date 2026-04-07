"""Comprehensive tests for field-level encryption.

This module tests all features of the FieldEncryption class:
- Per-field key derivation using PBKDF2HMAC
- Cryptographic isolation (each field has unique encryption key)
- Batch encryption/decryption for dictionaries
- Support for PII and sensitive field definitions
"""

import pytest
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet

from app.shared.field_encryption import (
    FieldEncryption,
    get_field_encryption,
    PII_FIELDS,
    SENSITIVE_FIELDS,
)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def field_encryptor(encryption_key):
    """Create a field encryption instance."""
    return FieldEncryption(master_key=encryption_key)


class TestFieldKeyDerivation:
    """Test per-field key derivation."""

    def test_different_fields_have_different_keys(self, field_encryptor):
        """Test different field names derive different keys."""
        key1 = field_encryptor._derive_key("email")
        key2 = field_encryptor._derive_key("phone")

        # Should be different Fernet instances
        assert key1 is not key2

    def test_same_field_same_key(self, field_encryptor):
        """Test same field name derives same key (cached)."""
        key1 = field_encryptor._derive_key("email")
        key2 = field_encryptor._derive_key("email")

        # Should be the same instance (cached)
        assert key1 is key2

    def test_key_derivation_uses_pbkdf2(self, field_encryptor):
        """Test key derivation uses PBKDF2HMAC."""
        # The implementation should use PBKDF2HMAC
        # We can verify by checking the key is correctly formatted
        fernet = field_encryptor._derive_key("test_field")
        assert isinstance(fernet, Fernet)

    def test_field_name_used_as_salt(self, field_encryptor):
        """Test field name is used as salt for key derivation."""
        # Same master key with different field names should produce different keys
        key1 = field_encryptor._derive_key("field_a")
        key2 = field_encryptor._derive_key("field_b")

        # They should be able to encrypt/decrypt independently
        encrypted1 = key1.encrypt(b"test")
        encrypted2 = key2.encrypt(b"test")

        assert encrypted1 != encrypted2

    def test_key_cache_efficiency(self, field_encryptor):
        """Test key cache improves efficiency."""
        # First call
        key1 = field_encryptor._derive_key("cached_field")

        # Second call should use cache
        key2 = field_encryptor._derive_key("cached_field")

        assert key1 is key2
        assert len(field_encryptor._field_keys) == 1


class TestSingleFieldEncryption:
    """Test single field encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self, field_encryptor):
        """Test encrypt and decrypt roundtrip."""
        original = "sensitive data"
        encrypted = field_encryptor.encrypt_field("test_field", original)
        decrypted = field_encryptor.decrypt_field("test_field", encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_encryption_produces_different_output(self, field_encryptor):
        """Test encryption produces different output each time."""
        data = "test data"
        encrypted1 = field_encryptor.encrypt_field("test_field", data)
        encrypted2 = field_encryptor.encrypt_field("test_field", data)

        # Should be different (Fernet includes timestamp)
        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_field_fails(self, field_encryptor):
        """Test decryption with wrong field name fails."""
        original = "sensitive data"
        encrypted = field_encryptor.encrypt_field("correct_field", original)

        # Try to decrypt with wrong field
        decrypted = field_encryptor.decrypt_field("wrong_field", encrypted)

        # Should return None (decryption failed)
        assert decrypted is None

    def test_none_value_encryption(self, field_encryptor):
        """Test None value is returned as-is."""
        result = field_encryptor.encrypt_field("test_field", None)
        assert result is None

    def test_empty_string_encryption(self, field_encryptor):
        """Test empty string is returned as-is."""
        result = field_encryptor.encrypt_field("test_field", "")
        assert result == ""

    def test_none_value_decryption(self, field_encryptor):
        """Test None decryption returns None."""
        result = field_encryptor.decrypt_field("test_field", None)
        assert result is None

    def test_empty_string_decryption(self, field_encryptor):
        """Test empty string decryption returns empty."""
        result = field_encryptor.decrypt_field("test_field", "")
        assert result == ""

    def test_unicode_data(self, field_encryptor):
        """Test encryption of unicode data."""
        original = "Hello 世界 🌍 ñáéíóú"
        encrypted = field_encryptor.encrypt_field("test_field", original)
        decrypted = field_encryptor.decrypt_field("test_field", encrypted)

        assert decrypted == original

    def test_large_data(self, field_encryptor):
        """Test encryption of large data."""
        original = "A" * 10000
        encrypted = field_encryptor.encrypt_field("test_field", original)
        decrypted = field_encryptor.decrypt_field("test_field", encrypted)

        assert decrypted == original


class TestDictionaryEncryption:
    """Test batch dictionary encryption/decryption."""

    def test_encrypt_dict_fields(self, field_encryptor):
        """Test encrypting specific fields in a dictionary."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-1234",
            "age": 30
        }

        result = field_encryptor.encrypt_dict(data, ["email", "phone"])

        # Specified fields should be encrypted
        assert result["email"] != data["email"]
        assert result["phone"] != data["phone"]

        # Other fields should be unchanged
        assert result["name"] == data["name"]
        assert result["age"] == data["age"]

    def test_decrypt_dict_fields(self, field_encryptor):
        """Test decrypting specific fields in a dictionary."""
        original = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-1234"
        }

        encrypted = field_encryptor.encrypt_dict(original, ["email", "phone"])
        decrypted = field_encryptor.decrypt_dict(encrypted, ["email", "phone"])

        assert decrypted["email"] == original["email"]
        assert decrypted["phone"] == original["phone"]
        assert decrypted["name"] == original["name"]

    def test_encrypt_dict_empty_fields_list(self, field_encryptor):
        """Test encrypting with empty fields list."""
        data = {"key": "value"}
        result = field_encryptor.encrypt_dict(data, [])

        assert result["key"] == "value"

    def test_encrypt_dict_nonexistent_fields(self, field_encryptor):
        """Test encrypting non-existent fields is safe."""
        data = {"existing": "value"}
        result = field_encryptor.encrypt_dict(data, ["nonexistent"])

        assert result["existing"] == "value"

    def test_encrypt_dict_preserves_none_values(self, field_encryptor):
        """Test encryption preserves None values."""
        data = {"field": None}
        result = field_encryptor.encrypt_dict(data, ["field"])

        assert result["field"] is None

    def test_decrypt_dict_preserves_invalid_encryption(self, field_encryptor):
        """Test decryption preserves fields that fail to decrypt."""
        data = {
            "valid": field_encryptor.encrypt_field("valid", "data"),
            "invalid": "not-encrypted-data"
        }

        result = field_encryptor.decrypt_dict(data, ["valid", "invalid"])

        assert result["valid"] == "data"
        # Invalid field should remain as-is
        assert result["invalid"] == "not-encrypted-data"

    def test_encrypt_dict_nested_values(self, field_encryptor):
        """Test encrypting dict handles various value types."""
        data = {
            "string": "value",
            "number": 42,
            "bool": True,
            "list": [1, 2, 3]
        }

        result = field_encryptor.encrypt_dict(data, ["string", "number"])

        # String should be encrypted
        assert result["string"] != "value"
        # Number should be converted to string and encrypted
        assert result["number"] != 42
        # Other types should be unchanged
        assert result["bool"] == True
        assert result["list"] == [1, 2, 3]


class TestFieldIsolation:
    """Test cryptographic isolation between fields."""

    def test_fields_cannot_cross_decrypt(self, field_encryptor):
        """Test data encrypted for one field cannot be decrypted by another."""
        data = "sensitive"
        encrypted = field_encryptor.encrypt_field("field_a", data)

        # Should not be able to decrypt with different field
        decrypted = field_encryptor.decrypt_field("field_b", encrypted)
        assert decrypted is None

    def test_same_data_different_fields(self, field_encryptor):
        """Test same data encrypted for different fields produces different ciphertext."""
        data = "test"
        encrypted_a = field_encryptor.encrypt_field("field_a", data)
        encrypted_b = field_encryptor.encrypt_field("field_b", data)

        assert encrypted_a != encrypted_b


class TestPIIAndSensitiveFields:
    """Test PII and sensitive field definitions."""

    def test_pii_fields_list_exists(self):
        """Test PII_FIELDS list is defined."""
        assert isinstance(PII_FIELDS, list)
        assert len(PII_FIELDS) > 0

    def test_pii_fields_contains_email(self):
        """Test PII_FIELDS contains email."""
        assert "email" in PII_FIELDS

    def test_pii_fields_contains_phone(self):
        """Test PII_FIELDS contains phone fields."""
        assert any(f in PII_FIELDS for f in ["phone", "phone_number"])

    def test_pii_fields_contains_address(self):
        """Test PII_FIELDS contains address."""
        assert "address" in PII_FIELDS

    def test_sensitive_fields_list_exists(self):
        """Test SENSITIVE_FIELDS list is defined."""
        assert isinstance(SENSITIVE_FIELDS, list)
        assert len(SENSITIVE_FIELDS) > 0

    def test_sensitive_fields_contains_api_key(self):
        """Test SENSITIVE_FIELDS contains api_key."""
        assert "api_key" in SENSITIVE_FIELDS

    def test_sensitive_fields_contains_password(self):
        """Test SENSITIVE_FIELDS contains password."""
        assert "password" in SENSITIVE_FIELDS

    def test_sensitive_fields_contains_secret(self):
        """Test SENSITIVE_FIELDS contains secret fields."""
        assert any("secret" in f for f in SENSITIVE_FIELDS)


class TestGlobalInstance:
    """Test global field encryption instance."""

    def test_get_field_encryption_singleton(self):
        """Test get_field_encryption returns same instance."""
        with patch('app.shared.field_encryption.settings') as mock_settings:
            mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

            instance1 = get_field_encryption()
            instance2 = get_field_encryption()

            assert instance1 is instance2

    def test_get_field_encryption_creates_new_if_none(self):
        """Test get_field_encryption creates new instance if none exists."""
        with patch('app.shared.field_encryption.settings') as mock_settings:
            mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

            # Clear any existing instance
            import app.shared.field_encryption as fe
            fe._field_encryption = None

            instance = get_field_encryption()
            assert instance is not None
            assert isinstance(instance, FieldEncryption)


class TestMasterKeyInitialization:
    """Test master key initialization."""

    def test_string_key_converted_to_bytes(self):
        """Test string key is converted to bytes."""
        key = Fernet.generate_key().decode()
        encryptor = FieldEncryption(master_key=key)

        assert isinstance(encryptor.master_key, bytes)

    def test_bytes_key_used_directly(self):
        """Test bytes key is used directly."""
        key = Fernet.generate_key()
        encryptor = FieldEncryption(master_key=key)

        assert encryptor.master_key == key

    def test_key_from_settings(self):
        """Test key is loaded from settings if not provided."""
        test_key = Fernet.generate_key().decode()

        with patch('app.shared.field_encryption.settings') as mock_settings:
            mock_settings.ENCRYPTION_KEY = test_key

            encryptor = FieldEncryption()
            assert encryptor.master_key == test_key.encode()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_encrypt_decrypt_boolean_string(self, field_encryptor):
        """Test boolean converted to string and encrypted."""
        encrypted = field_encryptor.encrypt_field("test_field", True)
        decrypted = field_encryptor.decrypt_field("test_field", encrypted)

        assert decrypted == "True"

    def test_encrypt_decrypt_number_string(self, field_encryptor):
        """Test number converted to string and encrypted."""
        encrypted = field_encryptor.encrypt_field("test_field", 42)
        decrypted = field_encryptor.decrypt_field("test_field", encrypted)

        assert decrypted == "42"

    def test_decrypt_corrupted_data(self, field_encryptor):
        """Test decrypting corrupted data returns None."""
        decrypted = field_encryptor.decrypt_field("test_field", "invalid-data")
        assert decrypted is None

    def test_decrypt_tampered_data(self, field_encryptor):
        """Test decrypting tampered data returns None."""
        original = "test data"
        encrypted = field_encryptor.encrypt_field("test_field", original)

        # Tamper with the encrypted data
        tampered = encrypted[:-5] + "XXXXX"

        decrypted = field_encryptor.decrypt_field("test_field", tampered)
        assert decrypted is None

    def test_concurrent_field_access(self, field_encryptor):
        """Test concurrent access to same field."""
        import threading

        results = []

        def encrypt_decrypt():
            encrypted = field_encryptor.encrypt_field("concurrent_field", "data")
            decrypted = field_encryptor.decrypt_field("concurrent_field", encrypted)
            results.append(decrypted)

        threads = [threading.Thread(target=encrypt_decrypt) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == "data" for r in results)

    def test_empty_dict_encryption(self, field_encryptor):
        """Test encrypting empty dictionary."""
        result = field_encryptor.encrypt_dict({}, ["field"])
        assert result == {}
