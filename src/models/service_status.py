"""Service status record model for historical status data."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from src.models.base import Base
from src.models.enums import ServiceStatus  # noqa: TC001

if TYPE_CHECKING:
    from src.models.service import Service


class ServiceStatusRecord(Base):
    """Historical record of a service's status at a point in time.

    Each poll of a service's status page creates one of these records,
    allowing historical analysis of uptime and performance.
    """

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Override auto-generated table name."""
        return "service_status"

    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ServiceStatus] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    checked_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    service: Mapped[Service] = relationship(
        "Service",
        back_populates="status_records",
    )

    __table_args__ = (
        Index("ix_service_status_service_checked", "service_id", "checked_at"),
        Index("ix_service_status_status_checked", "status", "checked_at"),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<ServiceStatusRecord(service_id={self.service_id}, status={self.status})>"
