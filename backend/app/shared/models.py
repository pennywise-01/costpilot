import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OptimisticLockingMixin:
    version_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def generate_uuid() -> str:
    return str(uuid.uuid4())


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
