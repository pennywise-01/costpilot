from datetime import datetime

from pydantic import BaseModel

from app.shared.enums import NotificationType
from app.shared.pagination import PaginatedResponse


class NotificationPrefItem(BaseModel):
    notification_type: NotificationType
    enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    preferences: list[NotificationPrefItem]


class NotificationPrefResponse(BaseModel):
    id: str
    notification_type: NotificationType
    enabled: bool

    model_config = {"from_attributes": True}


class NotificationPreferencesResponse(BaseModel):
    preferences: list[NotificationPrefResponse]


class NotificationLogResponse(BaseModel):
    id: str
    notification_type: NotificationType
    recipient_email: str
    subject: str
    sent_at: datetime | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogsResponse(BaseModel):
    logs: list[NotificationLogResponse]
    total: int


class PaginatedNotificationLogs(PaginatedResponse[NotificationLogResponse]):
    """Paginated response for notification logs."""
    pass


class SendTestEmailRequest(BaseModel):
    notification_type: NotificationType
