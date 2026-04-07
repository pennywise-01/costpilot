from sqlalchemy import Boolean, Integer, String, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import CloudType


class CloudAccount(BaseModel, OptimisticLockingMixin):
    __tablename__ = "cloud_accounts"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    type: Mapped[CloudType] = mapped_column(SAEnum(CloudType), nullable=False)
    config: Mapped[str] = mapped_column(Text, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    auto_import: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    import_period: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_import_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_import_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[str] = mapped_column(String(256), nullable=False)
    process_recommendations: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    organization = relationship("Organization", back_populates="cloud_accounts", lazy="selectin")
    cost_caches: Mapped[list["CostCache"]] = relationship(
        "CostCache", back_populates="cloud_account", lazy="selectin"
    )
