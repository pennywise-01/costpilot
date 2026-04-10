"""Comprehensive audit logging for security events."""

import hashlib
import json
from enum import Enum, auto
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
import logging

from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of auditable events."""
    # Authentication
    LOGIN_SUCCESS = auto()
    LOGIN_FAILURE = auto()
    LOGOUT = auto()
    TOKEN_REFRESH = auto()
    PASSWORD_CHANGE = auto()
    PASSWORD_RESET_REQUESTED = auto()
    MFA_ENABLED = auto()
    MFA_DISABLED = auto()
    MFA_CHALLENGE = auto()

    # Authorization
    PERMISSION_DENIED = auto()
    ROLE_ASSIGNED = auto()
    ROLE_REVOKED = auto()
    POLICY_CREATED = auto()
    POLICY_UPDATED = auto()
    POLICY_DELETED = auto()

    # Data Access
    DATA_EXPORTED = auto()
    DATA_IMPORTED = auto()
    RECORD_VIEWED = auto()
    RECORD_CREATED = auto()
    RECORD_MODIFIED = auto()
    RECORD_DELETED = auto()
    BULK_OPERATION = auto()

    # Admin Actions
    USER_CREATED = auto()
    USER_UPDATED = auto()
    USER_SUSPENDED = auto()
    USER_REACTIVATED = auto()
    USER_REMOVED = auto()
    ORG_CREATED = auto()
    ORG_UPDATED = auto()
    ORG_SETTINGS_CHANGED = auto()

    # Security Events
    SUSPICIOUS_ACTIVITY = auto()
    RATE_LIMIT_EXCEEDED = auto()
    SESSION_INVALIDATED = auto()
    TOKEN_REUSE_DETECTED = auto()
    IP_BLOCKED = auto()
    MFA_FAILURE = auto()
    BRUTE_FORCE_ATTEMPT = auto()

    # System Events
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    CONFIG_CHANGED = auto()
    BACKUP_CREATED = auto()
    BACKUP_RESTORED = auto()


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLogger:
    """Comprehensive audit logging for security events."""

    # Fields that should be redacted from logs
    SENSITIVE_FIELDS = {
        'password', 'secret', 'token', 'key', 'credential',
        'api_key', 'private_key', 'client_secret', 'auth_code',
        'credit_card', 'cvv', 'ssn', 'tax_id'
    }

    # Event types that should trigger alerts
    ALERT_SEVERITIES = {AuditSeverity.HIGH, AuditSeverity.CRITICAL}

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive data from log details."""
        if not details:
            return {}

        sanitized = {}
        for key, value in details.items():
            # Check if key contains sensitive field name
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, list):
                # Sanitize items in lists
                sanitized_list = []
                for item in value:
                    if isinstance(item, dict):
                        sanitized_list.append(self._sanitize_details(item))
                    else:
                        sanitized_list.append(item)
                sanitized[key] = sanitized_list
            else:
                sanitized[key] = value

        return sanitized

    def _hash_ip(self, ip: Optional[str]) -> Optional[str]:
        """Hash IP address for privacy."""
        if ip is None:
            return None
        # Use first 16 chars of SHA256 hash for privacy
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def _hash_user_agent(self, user_agent: Optional[str]) -> Optional[str]:
        """Hash user agent for privacy while keeping fingerprint capability."""
        if not user_agent:
            return None
        return hashlib.sha256(user_agent.encode()).hexdigest()[:16]

    async def log(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action_details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
    ) -> dict[str, Any]:
        """Log a security audit event.

        Args:
            db: Database session
            event_type: Type of security event
            severity: Severity level
            user_id: User ID associated with the event
            org_id: Organization ID
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            action_details: Additional event details
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session ID
            success: Whether the action succeeded

        Returns:
            The created audit event data
        """
        # Sanitize action details
        sanitized_details = self._sanitize_details(action_details or {})

        event = {
            "timestamp": utc_now(),
            "event_type": event_type.name,
            "severity": severity.value,
            "user_id": user_id,
            "organization_id": org_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action_details": json.dumps(sanitized_details) if sanitized_details else None,
            "ip_address_hash": self._hash_ip(ip_address),
            "user_agent_hash": self._hash_user_agent(user_agent),
            "session_id": session_id,
            "success": success,
        }

        # Log to Python logger
        log_message = f"Audit: {event_type.name} | User: {user_id} | Org: {org_id}"
        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_message, extra=event)
        elif severity == AuditSeverity.HIGH:
            logger.error(log_message, extra=event)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_message, extra=event)
        else:
            logger.info(log_message, extra=event)

        # Persist to database if session provided
        if db:
            try:
                await self._persist_event(db, event)
            except Exception as e:
                logger.error(f"Failed to persist audit event: {e}")

        # Send alert for high severity events
        if severity in self.ALERT_SEVERITIES:
            await self._send_security_alert(event)

        return event

    async def _persist_event(
        self,
        db: AsyncSession,
        event: dict[str, Any]
    ) -> None:
        """Persist event to database."""
        try:
            from app.security.models import AuditLog

            audit_entry = AuditLog(**event)
            db.add(audit_entry)
            await db.flush()
        except Exception as e:
            logger.error(f"Failed to persist audit event: {e}")
            raise

    async def _send_security_alert(self, event: dict[str, Any]) -> None:
        """Send real-time alert for critical security events."""
        # TODO: Integrate with notification service
        # This could send to Slack, PagerDuty, email, etc.
        logger.warning(f"SECURITY ALERT: {event['event_type']} - {event['severity']}")

    # Convenience methods for common events

    async def log_login(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Log login attempt."""
        return await self.log(
            db=db,
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            action_details={"failure_reason": failure_reason} if failure_reason else None
        )

    async def log_permission_denied(
        self,
        db: AsyncSession,
        user_id: str,
        org_id: Optional[str],
        resource_type: str,
        action: str,
        ip_address: Optional[str] = None
    ) -> dict[str, Any]:
        """Log permission denied event."""
        return await self.log(
            db=db,
            event_type=AuditEventType.PERMISSION_DENIED,
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            org_id=org_id,
            resource_type=resource_type,
            ip_address=ip_address,
            success=False,
            action_details={"attempted_action": action}
        )

    async def log_data_export(
        self,
        db: AsyncSession,
        user_id: str,
        org_id: str,
        export_type: str,
        record_count: int,
        ip_address: Optional[str] = None
    ) -> dict[str, Any]:
        """Log data export event."""
        return await self.log(
            db=db,
            event_type=AuditEventType.DATA_EXPORTED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            org_id=org_id,
            ip_address=ip_address,
            success=True,
            action_details={
                "export_type": export_type,
                "record_count": record_count
            }
        )

    async def log_suspicious_activity(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        activity_type: str,
        details: dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> dict[str, Any]:
        """Log suspicious activity."""
        return await self.log(
            db=db,
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            action_details={
                "activity_type": activity_type,
                **details
            }
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
