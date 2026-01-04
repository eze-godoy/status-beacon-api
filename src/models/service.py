"""Service model for tracking monitored cloud services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.incident import Incident
    from src.models.service_status import ServiceStatusRecord


class Service(Base, TimestampMixin):
    """Cloud service being monitored.

    Represents a third-party service (AWS, GCP, Azure, etc.) whose
    status page we poll for health information.
    """

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    status_records: Mapped[list[ServiceStatusRecord]] = relationship(
        "ServiceStatusRecord",
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incidents: Mapped[list[Incident]] = relationship(
        "Incident",
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_service_provider_active", "provider", "is_active"),)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Service(name={self.name!r}, provider={self.provider!r})>"
