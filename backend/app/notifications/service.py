import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.shared.enums import NotificationType
from app.shared.exceptions import BadRequestError
from app.notifications.models import NotificationPreference, NotificationLog
from app.notifications.schemas import NotificationPrefItem
from app.notifications.email_service import RENDERERS, send_email

logger = logging.getLogger(__name__)

# Default enabled state for each notification type (matches frontend defaults)
DEFAULT_PREFS: dict[NotificationType, bool] = {
    NotificationType.BUDGET_ALERTS: True,
    NotificationType.RECOMMENDATION_UPDATES: True,
    NotificationType.DAILY_COST_SUMMARY: False,
    NotificationType.WEEKLY_REPORT: True,
    NotificationType.ANOMALY_ALERTS: True,
    NotificationType.NEW_USER_JOINED: False,
}


async def get_preferences(
    db: AsyncSession, user_id: str, org_id: str
) -> list[NotificationPreference]:
    """Get all notification preferences for a user in an org, creating defaults if none exist."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.organization_id == org_id,
            NotificationPreference.deleted_at.is_(None),
        )
    )
    prefs = list(result.scalars().all())

    if not prefs:
        prefs = []
        for ntype, enabled in DEFAULT_PREFS.items():
            pref = NotificationPreference(
                user_id=user_id,
                organization_id=org_id,
                notification_type=ntype,
                enabled=enabled,
            )
            db.add(pref)
            prefs.append(pref)
        await db.flush()

    return prefs


async def update_preferences(
    db: AsyncSession, user_id: str, org_id: str, items: list[NotificationPrefItem]
) -> list[NotificationPreference]:
    """Upsert notification preferences for a user in an org."""
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.organization_id == org_id,
            NotificationPreference.deleted_at.is_(None),
        )
    )
    existing = {p.notification_type: p for p in result.scalars().all()}

    prefs = []
    for item in items:
        if item.notification_type in existing:
            existing[item.notification_type].enabled = item.enabled
            prefs.append(existing[item.notification_type])
        else:
            pref = NotificationPreference(
                user_id=user_id,
                organization_id=org_id,
                notification_type=item.notification_type,
                enabled=item.enabled,
            )
            db.add(pref)
            prefs.append(pref)
    await db.flush()
    return prefs


async def get_notification_logs(
    db: AsyncSession, user_id: str, org_id: str, limit: int = 50, offset: int = 0
) -> tuple[list[NotificationLog], int]:
    """Get notification history for a user in an org with pagination."""
    count_result = await db.execute(
        select(func.count()).select_from(NotificationLog).where(
            NotificationLog.user_id == user_id,
            NotificationLog.organization_id == org_id,
            NotificationLog.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(NotificationLog)
        .where(
            NotificationLog.user_id == user_id,
            NotificationLog.organization_id == org_id,
            NotificationLog.deleted_at.is_(None),
        )
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = list(result.scalars().all())
    return logs, total


async def send_notification(
    db: AsyncSession,
    user: User,
    org_id: str,
    notification_type: NotificationType,
    data: dict,
) -> NotificationLog:
    """Send a notification email to a user if they have it enabled.

    Returns the NotificationLog entry.
    """
    # Check preference
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user.id,
            NotificationPreference.organization_id == org_id,
            NotificationPreference.notification_type == notification_type,
            NotificationPreference.deleted_at.is_(None),
        )
    )
    pref = result.scalar_one_or_none()

    # If no preference exists, use the default
    enabled = pref.enabled if pref else DEFAULT_PREFS.get(notification_type, False)

    if not enabled:
        logger.debug(
            "Notification %s disabled for user %s, skipping", notification_type, user.id
        )
        return None

    renderer = RENDERERS.get(notification_type)
    if not renderer:
        raise BadRequestError(f"Unknown notification type: {notification_type}")

    subject, html_body = renderer(data)

    log = NotificationLog(
        user_id=user.id,
        organization_id=org_id,
        notification_type=notification_type,
        recipient_email=user.email,
        subject=subject,
        body=html_body,
    )
    db.add(log)

    try:
        await send_email(user.email, subject, html_body)
        log.sent_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", user.email, exc)
        log.error = str(exc)

    await db.flush()
    return log


async def send_test_notification(
    db: AsyncSession,
    user: User,
    org_id: str,
    notification_type: NotificationType,
) -> NotificationLog:
    """Send a test notification with sample data."""
    sample_data = _get_sample_data(notification_type)
    # For test emails, bypass preference check — send directly
    renderer = RENDERERS.get(notification_type)
    if not renderer:
        raise BadRequestError(f"Unknown notification type: {notification_type}")

    subject, html_body = renderer(sample_data)
    subject = f"[TEST] {subject}"

    log = NotificationLog(
        user_id=user.id,
        organization_id=org_id,
        notification_type=notification_type,
        recipient_email=user.email,
        subject=subject,
        body=html_body,
    )
    db.add(log)

    try:
        await send_email(user.email, subject, html_body)
        log.sent_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.error("Failed to send test email to %s: %s", user.email, exc)
        log.error = str(exc)

    await db.flush()
    return log


def _get_sample_data(notification_type: NotificationType) -> dict:
    """Return sample data for test notifications."""
    samples = {
        NotificationType.BUDGET_ALERTS: {
            "budget_name": "Production AWS",
            "current_spend": 8500.00,
            "budget_limit": 10000.00,
            "top_drivers": [
                {"name": "EC2 Instances", "cost": 3200.00},
                {"name": "RDS", "cost": 2100.00},
                {"name": "S3 Storage", "cost": 1400.00},
            ],
            "dashboard_url": "#",
        },
        NotificationType.RECOMMENDATION_UPDATES: {
            "count": 3,
            "total_savings": 420.00,
            "recommendations": [
                {"resource": "i-0abc123 (m5.xlarge)", "type": "Right-size", "savings": 180.00},
                {"resource": "vol-xyz789 (500GB gp2)", "type": "Migrate to gp3", "savings": 140.00},
                {"resource": "db-prod-01 (db.r5.large)", "type": "Reserved Instance", "savings": 100.00},
            ],
            "dashboard_url": "#",
        },
        NotificationType.DAILY_COST_SUMMARY: {
            "date": "Mar 14, 2026",
            "total_spend": 1234.56,
            "avg_spend": 1175.00,
            "by_provider": [
                {"name": "AWS", "cost": 890.00},
                {"name": "Azure", "cost": 244.56},
                {"name": "GCP", "cost": 100.00},
            ],
            "top_services": [
                {"name": "EC2", "cost": 450.00},
                {"name": "RDS", "cost": 220.00},
                {"name": "Azure VMs", "cost": 180.00},
                {"name": "S3", "cost": 130.00},
                {"name": "CloudSQL", "cost": 85.00},
            ],
            "dashboard_url": "#",
        },
        NotificationType.WEEKLY_REPORT: {
            "week_range": "Mar 8 – 14, 2026",
            "total_spend": 8750.00,
            "prev_week_spend": 9020.00,
            "top_movers": [
                {"name": "EC2", "cost": 3200.00, "change": -5.2},
                {"name": "Lambda", "cost": 480.00, "change": 22.3},
                {"name": "RDS", "cost": 2100.00, "change": -1.1},
            ],
            "open_recommendations": 7,
            "potential_savings": 1250.00,
            "dashboard_url": "#",
        },
        NotificationType.ANOMALY_ALERTS: {
            "service": "EC2",
            "region": "us-east-1",
            "expected_spend": 120.00,
            "actual_spend": 528.00,
            "started_at": "Mar 14, 2026 at 09:15 UTC",
            "possible_causes": [
                "4 new c5.2xlarge instances launched",
                "Auto-scaling group scaled beyond expected range",
            ],
            "dashboard_url": "#",
        },
        NotificationType.NEW_USER_JOINED: {
            "user_name": "Jane Smith",
            "user_email": "jane@company.com",
            "role": "Member",
            "invited_by": "admin@company.com",
            "dashboard_url": "#",
        },
    }
    return samples.get(notification_type, {})
