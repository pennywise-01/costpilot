"""Session security validation and binding."""

import hashlib
import hmac
from typing import Optional
from fastapi import Request

from app.config import settings


class SessionSecurityValidator:
    """Additional session security checks with fingerprint binding."""

    def __init__(self):
        self.max_session_age_hours = getattr(settings, "MAX_SESSION_AGE_HOURS", 24)
        self.require_ip_binding = getattr(settings, "REQUIRE_IP_BINDING", True)
        self.require_fingerprint_binding = getattr(settings, "REQUIRE_FINGERPRINT_BINDING", True)

    def generate_session_fingerprint(self, request: Request) -> str:
        """Generate unique fingerprint for session binding.
        
        Combines multiple factors to create a browser/device fingerprint.
        """
        components = [
            request.client.host if request.client else "",
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("accept-encoding", ""),
            request.headers.get("dnt", ""),  # Do Not Track
        ]
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode()).hexdigest()

    def validate_session_binding(
        self,
        request: Request,
        stored_fingerprint: str | None,
        stored_ip: str | None = None,
        strict_mode: bool = False
    ) -> tuple[bool, Optional[str]]:
        """Validate session hasn't been hijacked.
        
        Returns:
            Tuple of (is_valid, failure_reason)
        """
        if not self.require_fingerprint_binding and not self.require_ip_binding:
            return True, None

        current_fingerprint = self.generate_session_fingerprint(request)
        current_ip = request.client.host if request.client else None

        # Validate IP binding (if enabled and stored IP exists)
        if self.require_ip_binding and stored_ip and current_ip:
            if not self._validate_ip_binding(stored_ip, current_ip, strict_mode):
                return False, "IP_ADDRESS_MISMATCH"

        # Validate fingerprint binding
        if self.require_fingerprint_binding and stored_fingerprint:
            if not hmac.compare_digest(stored_fingerprint, current_fingerprint):
                # In lenient mode, allow fingerprint drift when IP remains in
                # the same subnet (common with NAT/mobile network behavior).
                if (
                    not strict_mode
                    and stored_ip
                    and current_ip
                    and self._ips_in_same_subnet(stored_ip, current_ip)
                ):
                    return True, None

                # Check if it's just a minor UA change (e.g., browser update)
                if not self._is_minor_ua_change(stored_fingerprint, current_fingerprint):
                    return False, "FINGERPRINT_MISMATCH"

        return True, None

    def _validate_ip_binding(
        self,
        stored_ip: str,
        current_ip: str,
        strict_mode: bool = False
    ) -> bool:
        """Validate IP address binding.
        
        In non-strict mode, allows IPs from same /24 subnet (likely same network).
        In strict mode, requires exact match.
        """
        if stored_ip == current_ip:
            return True

        if strict_mode:
            return False

        # Check if IPs are from same /24 subnet
        return self._ips_in_same_subnet(stored_ip, current_ip)

    def _ips_in_same_subnet(self, ip1: str, ip2: str) -> bool:
        """Check if IPs are in the same /24 subnet."""
        try:
            parts1 = ip1.split(".")
            parts2 = ip2.split(".")
            # For IPv4, compare first 3 octets
            if len(parts1) == 4 and len(parts2) == 4:
                return parts1[:3] == parts2[:3]
            return ip1 == ip2
        except Exception:
            return ip1 == ip2

    def _is_minor_ua_change(self, fingerprint1: str, fingerprint2: str) -> bool:
        """Check if fingerprint change is minor (e.g., browser update)."""
        # This is a simplified check - in production, you might want to
        # decode the fingerprints and compare individual components
        # For now, we consider any change significant
        return False


class SessionBindingMiddleware:
    """Middleware to validate session binding on each request."""

    def __init__(self):
        self.validator = SessionSecurityValidator()

    async def validate_request(self, request: Request, session_data: dict) -> bool:
        """Validate session binding for a request."""
        stored_fingerprint = session_data.get("fingerprint")
        stored_ip = session_data.get("ip_address")

        is_valid, failure_reason = self.validator.validate_session_binding(
            request,
            stored_fingerprint,
            stored_ip,
            strict_mode=session_data.get("strict_mode", False)
        )

        if not is_valid:
            # Log security event
            # TODO: Integrate with audit logger
            pass

        return is_valid
