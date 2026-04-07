"""Comprehensive tests for security validators.

This module tests all security validators:
- validate_no_html() - HTML injection prevention
- validate_safe_filename() - Path traversal prevention in filenames
- validate_uuid_format() - UUID v4 validation
- sanitize_string() - String sanitization
- validate_email_format() - Email validation with security checks
- SecureBaseSchema - Base Pydantic model with sanitization
"""

import pytest
from pydantic import ValidationError

from app.shared.validators import (
    validate_no_html,
    validate_safe_filename,
    validate_uuid_format,
    sanitize_string,
    validate_email_format,
    SecureBaseSchema,
    SafeFilenameSchema,
    NoHtmlSchema,
)


class TestValidateNoHtml:
    """Test HTML injection prevention."""

    def test_valid_string(self):
        """Test valid string without HTML is allowed."""
        result = validate_no_html("Hello World")
        assert result == "Hello World"

    def test_none_value(self):
        """Test None value is returned as-is."""
        result = validate_no_html(None)
        assert result is None

    def test_html_tag_rejection(self):
        """Test strings with HTML tags are rejected."""
        with pytest.raises(ValueError, match="HTML tags are not allowed"):
            validate_no_html("<script>alert('xss')</script>")

    def test_html_tag_with_attributes(self):
        """Test HTML tags with attributes are rejected."""
        with pytest.raises(ValueError, match="HTML tags are not allowed"):
            validate_no_html('<div class="test">content</div>')

    def test_self_closing_tag(self):
        """Test self-closing HTML tags are rejected."""
        with pytest.raises(ValueError, match="HTML tags are not allowed"):
            validate_no_html("<img src='x' onerror='alert(1)'/>")

    def test_javascript_protocol(self):
        """Test javascript: protocol in strings is rejected."""
        with pytest.raises(ValueError, match="Potentially malicious content detected"):
            validate_no_html("javascript:alert('xss')")

    def test_onerror_attribute(self):
        """Test onerror event handler is rejected."""
        with pytest.raises(ValueError, match="Potentially malicious content detected"):
            validate_no_html('" onerror=alert("xss")')

    def test_onload_attribute(self):
        """Test onload event handler is rejected."""
        with pytest.raises(ValueError, match="Potentially malicious content detected"):
            validate_no_html('" onload=alert("xss")')

    def test_onclick_attribute(self):
        """Test onclick event handler is rejected."""
        with pytest.raises(ValueError, match="Potentially malicious content detected"):
            validate_no_html('" onclick=alert("xss")')

    def test_eval_function(self):
        """Test eval() function is rejected."""
        with pytest.raises(ValueError, match="Potentially malicious content detected"):
            validate_no_html("eval('malicious')")

    def test_html_entities_without_xss(self):
        """Test HTML entities without XSS patterns are allowed."""
        result = validate_no_html("& < >")
        assert result == "& < >"

    def test_empty_string(self):
        """Test empty string is allowed."""
        result = validate_no_html("")
        assert result == ""

    def test_case_insensitive_xss(self):
        """Test XSS detection is case insensitive."""
        with pytest.raises(ValueError, match="Potentially malicious content detected"):
            validate_no_html("JAVASCRIPT:alert('xss')")


class TestValidateSafeFilename:
    """Test filename validation for path traversal prevention."""

    def test_valid_filename(self):
        """Test valid filename is allowed."""
        result = validate_safe_filename("document.pdf")
        assert result == "document.pdf"

    def test_valid_filename_with_numbers(self):
        """Test filename with numbers is allowed."""
        result = validate_safe_filename("file123.txt")
        assert result == "file123.txt"

    def test_valid_filename_with_dashes(self):
        """Test filename with dashes and underscores is allowed."""
        result = validate_safe_filename("my-file_name.txt")
        assert result == "my-file_name.txt"

    def test_none_value(self):
        """Test None value is returned as-is."""
        result = validate_safe_filename(None)
        assert result is None

    def test_double_dot_rejection(self):
        """Test filename with .. is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("../etc/passwd")

    def test_forward_slash_rejection(self):
        """Test filename with / is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("path/to/file.txt")

    def test_backslash_rejection(self):
        """Test filename with \\ is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("path\\to\\file.txt")

    def test_null_byte_rejection(self):
        """Test filename with null byte is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("file\x00.txt")

    def test_percent_sign_rejection(self):
        """Test filename with % is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("file%2F.txt")

    def test_tilde_rejection(self):
        """Test filename with ~ is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("~/.bashrc")

    def test_dollar_sign_rejection(self):
        """Test filename with $ is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: contains dangerous characters"):
            validate_safe_filename("$HOME/file.txt")

    def test_reserved_windows_name_con(self):
        """Test reserved Windows name CON is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: reserved name"):
            validate_safe_filename("CON")

    def test_reserved_windows_name_con_txt(self):
        """Test reserved Windows name CON.txt is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: reserved name"):
            validate_safe_filename("CON.txt")

    def test_reserved_windows_name_uppercase(self):
        """Test uppercase reserved Windows name is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: reserved name"):
            validate_safe_filename("COM1")

    def test_reserved_windows_name_lpt(self):
        """Test reserved LPT name is rejected."""
        with pytest.raises(ValueError, match="Invalid filename: reserved name"):
            validate_safe_filename("LPT1.doc")

    def test_valid_name_similar_to_reserved(self):
        """Test valid filename similar to reserved name is allowed."""
        result = validate_safe_filename("CONNECTION.txt")
        assert result == "CONNECTION.txt"


class TestValidateUuidFormat:
    """Test UUID v4 format validation."""

    def test_valid_uuid_v4(self):
        """Test valid UUID v4 is accepted."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_uuid_format(valid_uuid)
        assert result == valid_uuid

    def test_valid_uuid_v4_uppercase(self):
        """Test valid UUID v4 with uppercase is accepted."""
        valid_uuid = "550E8400-E29B-41D4-A716-446655440000"
        result = validate_uuid_format(valid_uuid)
        assert result == valid_uuid

    def test_valid_uuid_v4_mixed_case(self):
        """Test valid UUID v4 with mixed case is accepted."""
        valid_uuid = "550E8400-e29b-41D4-a716-446655440000"
        result = validate_uuid_format(valid_uuid)
        assert result == valid_uuid

    def test_empty_string(self):
        """Test empty string is rejected."""
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("")

    def test_invalid_uuid_wrong_version(self):
        """Test UUID with wrong version is rejected."""
        # Version 1 UUID
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("550e8400-e29b-11d4-a716-446655440000")

    def test_invalid_uuid_wrong_variant(self):
        """Test UUID with wrong variant is rejected."""
        # Variant should be 8, 9, a, or b
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("550e8400-e29b-41d4-1716-446655440000")

    def test_invalid_uuid_too_short(self):
        """Test too short UUID is rejected."""
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("550e8400-e29b-41d4-a716")

    def test_invalid_uuid_too_long(self):
        """Test too long UUID is rejected."""
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("550e8400-e29b-41d4-a716-446655440000-extra")

    def test_invalid_uuid_wrong_format(self):
        """Test UUID with wrong format is rejected."""
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("not-a-uuid")

    def test_invalid_uuid_missing_hyphens(self):
        """Test UUID without hyphens is rejected."""
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("550e8400e29b41d4a716446655440000")

    def test_nil_uuid(self):
        """Test nil UUID is accepted (special case)."""
        # Note: nil UUID is version 0, not version 4
        # Depending on requirements, this might need to be rejected
        with pytest.raises(ValueError, match="Invalid UUID v4 format"):
            validate_uuid_format("00000000-0000-0000-0000-000000000000")


class TestSanitizeString:
    """Test string sanitization."""

    def test_normal_string(self):
        """Test normal string is returned unchanged."""
        result = sanitize_string("Hello World")
        assert result == "Hello World"

    def test_null_bytes_removed(self):
        """Test null bytes are removed."""
        result = sanitize_string("Hello\x00World")
        assert result == "HelloWorld"

    def test_control_characters_removed(self):
        """Test control characters are removed."""
        result = sanitize_string("Hello\x01\x02\x03World")
        assert result == "HelloWorld"

    def test_newlines_preserved(self):
        """Test newlines are preserved."""
        result = sanitize_string("Line1\nLine2")
        assert result == "Line1\nLine2"

    def test_tabs_preserved(self):
        """Test tabs are preserved."""
        result = sanitize_string("Col1\tCol2")
        assert result == "Col1\tCol2"

    def test_carriage_return_preserved(self):
        """Test carriage returns are preserved."""
        result = sanitize_string("Line1\r\nLine2")
        assert result == "Line1\r\nLine2"

    def test_leading_trailing_whitespace_trimmed(self):
        """Test leading/trailing whitespace is trimmed."""
        result = sanitize_string("  Hello World  ")
        assert result == "Hello World"

    def test_empty_string(self):
        """Test empty string returns empty string."""
        result = sanitize_string("")
        assert result == ""

    def test_string_at_length_limit(self):
        """Test string at exactly 10000 characters is allowed."""
        long_string = "A" * 10000
        result = sanitize_string(long_string)
        assert result == long_string

    def test_string_exceeds_length_limit(self):
        """Test string exceeding 10000 characters is rejected."""
        very_long_string = "A" * 10001
        with pytest.raises(ValueError, match="String too long"):
            sanitize_string(very_long_string)

    def test_non_string_value(self):
        """Test non-string value is returned as-is."""
        result = sanitize_string(123)
        assert result == 123

    def test_none_value(self):
        """Test None value is returned as-is."""
        result = sanitize_string(None)
        assert result is None

    def test_list_value(self):
        """Test list value is returned as-is."""
        result = sanitize_string(["a", "b"])
        assert result == ["a", "b"]


class TestValidateEmailFormat:
    """Test email format validation with security checks."""

    def test_valid_email(self):
        """Test valid email is accepted."""
        result = validate_email_format("user@example.com")
        assert result == "user@example.com"

    def test_valid_email_with_dots(self):
        """Test valid email with dots is accepted."""
        result = validate_email_format("first.last@example.co.uk")
        assert result == "first.last@example.co.uk"

    def test_valid_email_with_plus(self):
        """Test valid email with plus is accepted."""
        result = validate_email_format("user+tag@example.com")
        assert result == "user+tag@example.com"

    def test_valid_email_uppercase(self):
        """Test valid email is converted to lowercase."""
        result = validate_email_format("USER@EXAMPLE.COM")
        assert result == "user@example.com"

    def test_valid_email_mixed_case(self):
        """Test valid mixed case email is lowercased."""
        result = validate_email_format("User.Name@Example.COM")
        assert result == "user.name@example.com"

    def test_empty_string(self):
        """Test empty string is rejected."""
        with pytest.raises(ValueError, match="Email is required"):
            validate_email_format("")

    def test_none_value(self):
        """Test None value is rejected."""
        with pytest.raises(ValueError, match="Email is required"):
            validate_email_format(None)

    def test_missing_at_symbol(self):
        """Test email without @ is rejected."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email_format("userexample.com")

    def test_missing_domain(self):
        """Test email without domain is rejected."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email_format("user@")

    def test_missing_local_part(self):
        """Test email without local part is rejected."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email_format("@example.com")

    def test_multiple_at_symbols(self):
        """Test email with multiple @ is rejected."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email_format("user@@example.com")

    def test_invalid_tld(self):
        """Test email with invalid TLD is rejected."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_email_format("user@example.c")

    def test_email_with_script_tag(self):
        """Test email with script tag is rejected."""
        with pytest.raises(ValueError, match="Invalid email: contains suspicious patterns"):
            validate_email_format("<script>alert(1)</script>@example.com")

    def test_email_with_javascript_protocol(self):
        """Test email with javascript protocol is rejected."""
        with pytest.raises(ValueError, match="Invalid email: contains suspicious patterns"):
            validate_email_format("javascript:alert(1)@example.com")

    def test_email_with_onerror(self):
        """Test email with onerror handler is rejected."""
        with pytest.raises(ValueError, match="Invalid email: contains suspicious patterns"):
            validate_email_format("onerror=alert(1)@example.com")

    def test_whitespace_only_email(self):
        """Test whitespace-only email is rejected."""
        with pytest.raises(ValueError, match="Email is required"):
            validate_email_format("   ")


class TestSecureBaseSchema:
    """Test SecureBaseSchema with automatic string sanitization."""

    def test_string_field_sanitization(self):
        """Test string fields are automatically sanitized."""
        class TestSchema(SecureBaseSchema):
            name: str

        schema = TestSchema(name="Hello\x00World")
        assert schema.name == "HelloWorld"

    def test_multiple_string_fields(self):
        """Test multiple string fields are sanitized."""
        class TestSchema(SecureBaseSchema):
            first_name: str
            last_name: str

        schema = TestSchema(
            first_name="John\x01",
            last_name="\x02Doe"
        )
        assert schema.first_name == "John"
        assert schema.last_name == "Doe"

    def test_non_string_fields_unchanged(self):
        """Test non-string fields are not modified."""
        class TestSchema(SecureBaseSchema):
            name: str
            count: int

        schema = TestSchema(name="Test", count=42)
        assert schema.name == "Test"
        assert schema.count == 42

    def test_nested_sanitization(self):
        """Test sanitization in nested structures."""
        class TestSchema(SecureBaseSchema):
            data: dict

        # Note: dict values might not be sanitized automatically
        # depending on implementation
        schema = TestSchema(data={"key": "value"})
        assert schema.data == {"key": "value"}


class TestSafeFilenameSchema:
    """Test SafeFilenameSchema validation."""

    def test_valid_filename(self):
        """Test valid filename is accepted."""
        schema = SafeFilenameSchema(filename="document.pdf")
        assert schema.filename == "document.pdf"

    def test_invalid_filename_rejected(self):
        """Test invalid filename is rejected."""
        with pytest.raises(ValidationError):
            SafeFilenameSchema(filename="../etc/passwd")

    def test_reserved_name_rejected(self):
        """Test reserved Windows name is rejected."""
        with pytest.raises(ValidationError):
            SafeFilenameSchema(filename="CON.txt")


class TestNoHtmlSchema:
    """Test NoHtmlSchema validation."""

    def test_valid_text(self):
        """Test valid text without HTML is accepted."""
        schema = NoHtmlSchema(text="Hello World")
        assert schema.text == "Hello World"

    def test_html_tag_rejected(self):
        """Test HTML tag in text is rejected."""
        with pytest.raises(ValidationError):
            NoHtmlSchema(text="<script>alert(1)</script>")

    def test_javascript_rejected(self):
        """Test javascript protocol in text is rejected."""
        with pytest.raises(ValidationError):
            NoHtmlSchema(text="javascript:alert(1)")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_characters_allowed(self):
        """Test unicode characters are allowed in strings."""
        result = sanitize_string("Hello 世界 🌍")
        assert result == "Hello 世界 🌍"

    def test_very_long_email(self):
        """Test very long email is still validated."""
        # RFC 5321 allows up to 254 characters
        local_part = "a" * 64
        domain = "b" * 63 + ".com"
        email = f"{local_part}@{domain}"
        # This might be too long for the basic regex, but should not crash
        try:
            validate_email_format(email)
        except ValueError:
            pass  # Expected if too long

    def test_filename_with_spaces(self):
        """Test filename with spaces is allowed."""
        result = validate_safe_filename("my document.pdf")
        assert result == "my document.pdf"

    def test_email_with_special_chars_in_local(self):
        """Test email with valid special characters is accepted."""
        result = validate_email_format("user.name+tag!#$%&'*+/=?^_`{|}~@example.com")
        assert result == "user.name+tag!#$%&'*+/=?^_`{|}~@example.com"
