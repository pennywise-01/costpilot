"""Security-focused validators for input sanitization."""

import re
from typing import Any
from pydantic import field_validator, BaseModel


# Security-focused validators

def validate_no_html(value: str | None) -> str | None:
    """Prevent HTML injection in string fields."""
    if value is None:
        return value

    # Check for actual HTML tags (require a leading letter in tag name)
    if re.search(r'<\s*/?\s*[a-zA-Z][^>]*>', value):
        raise ValueError("HTML tags are not allowed")

    # Block common XSS/script patterns regardless of HTML entities
    suspicious = ['javascript:', 'onerror=', 'onload=', 'onclick=', 'eval(']
    lower_value = value.lower()
    for pattern in suspicious:
        if pattern in lower_value:
            raise ValueError(f"Potentially malicious content detected: {pattern}")

    return value


def validate_safe_filename(filename: str | None) -> str | None:
    """Prevent path traversal in filenames."""
    if filename is None:
        return filename
    
    dangerous_patterns = ['..', '/', '\\', '\x00', '%', '~', '$']
    if any(pattern in filename for pattern in dangerous_patterns):
        raise ValueError("Invalid filename: contains dangerous characters")
    
    # Check for reserved Windows filenames
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    name_without_ext = filename.split('.')[0].upper()
    if name_without_ext in reserved:
        raise ValueError("Invalid filename: reserved name")
    
    return filename


def validate_uuid_format(value: str) -> str:
    """Validate UUID v4 format."""
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    if not re.match(pattern, value, re.IGNORECASE):
        raise ValueError("Invalid UUID v4 format")
    return value


def sanitize_string(value: Any) -> Any:
    """Sanitize string values by removing null bytes and normalizing."""
    if isinstance(value, str):
        # Remove null bytes
        value = value.replace('\x00', '')
        # Remove control characters except newlines and tabs
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\t\r')
        # Normalize unicode
        value = value.strip()
        # Limit length for safety
        if len(value) > 10000:
            raise ValueError("String too long (max 10000 characters)")
    return value


def validate_email_format(email: str) -> str:
    """Validate email format with security checks."""
    if email is None:
        raise ValueError("Email is required")

    normalized_email = email.strip()
    if not normalized_email:
        raise ValueError("Email is required")

    lower_email = normalized_email.lower()

    # Check for common attack patterns before format validation so callers get
    # explicit security failure reasons.
    if any(pattern in lower_email for pattern in ["<script", "javascript:", "onerror="]):
        raise ValueError("Invalid email: contains suspicious patterns")
    
    # RFC-like email pattern with broad support for valid local-part symbols.
    pattern = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, normalized_email):
        raise ValueError("Invalid email format")

    return lower_email


class SecureBaseSchema(BaseModel):
    """Base schema with security validators."""

    @field_validator('*', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        """Sanitize all string fields."""
        return sanitize_string(v)


class SafeFilenameSchema(BaseModel):
    """Schema for filenames with security validation."""
    filename: str

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        return validate_safe_filename(v)


class NoHtmlSchema(BaseModel):
    """Schema for text fields that should not contain HTML."""
    text: str

    @field_validator('text')
    @classmethod
    def validate_no_html(cls, v):
        return validate_no_html(v)
