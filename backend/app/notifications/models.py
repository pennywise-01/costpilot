from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import NotificationType


class NotificationPreference(BaseModel, OptimisticLockingMixin):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notificationtype", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", "notification_type",
            name="uq_notification_pref_user_org_type",
        ),
    )


class NotificationLog(BaseModel):
    __tablename__ = "notification_logs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notificationtype", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    recipient_email: Mapped[str] = mapped_column(String(256), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
