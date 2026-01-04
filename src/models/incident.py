"""Incident model for tracking service outages and issues."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin
from src.models.enums import IncidentImpact, IncidentStatus

if TYPE_CHECKING:
    from src.models.service import Service


class Incident(Base, TimestampMixin):
    """Incident affecting a monitored service.

    Tracks outages, degraded performance, and maintenance windows
    reported by third-party status pages.
    """

    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    impact: Mapped[IncidentImpact] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    service: Mapped[Service] = relationship(
        "Service",
        back_populates="incidents",
    )

    __table_args__ = (
        Index(
            "uq_incident_service_external",
            "service_id",
            "external_id",
            unique=True,
        ),
        Index("ix_incident_status_created", "status", "created_at"),
        Index("ix_incident_service_status", "service_id", "status"),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Incident(title={self.title!r}, status={self.status})>"

    @property
    def is_resolved(self) -> bool:
        """Check if incident is resolved."""
        return self.status == IncidentStatus.RESOLVED
