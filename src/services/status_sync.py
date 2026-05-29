"""Service for synchronizing status from providers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.incident import Incident
from src.models.service import Service
from src.models.service_status import ServiceStatusRecord
from src.providers.base import ProviderIncident, ProviderStatusResult
from src.providers.exceptions import ProviderError
from src.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class StatusSyncService:
    """Service for fetching and persisting service status."""

    def __init__(self, registry: ProviderRegistry) -> None:
        """Initialize with provider registry.

        Args:
            registry: Provider registry for looking up providers.
        """
        self._registry = registry

    async def fetch_status(self, service: Service) -> ProviderStatusResult:
        """Fetch current status for a service (on-demand).

        Args:
            service: The service to fetch status for.

        Returns:
            ProviderStatusResult from the provider.

        Raises:
            ProviderNotFoundError: If service's provider not registered.
            ProviderError: On fetch failure.
        """
        provider = self._registry.get(service.provider)
        return await provider.fetch_status(service.status_url)

    async def sync_status(
        self,
        session: AsyncSession,
        service: Service,
    ) -> ServiceStatusRecord:
        """Fetch and persist status for a service.

        Args:
            session: Database session.
            service: The service to sync.

        Returns:
            Created ServiceStatusRecord.
        """
        result = await self.fetch_status(service)

        # Convert timezone-aware datetime to naive (database uses TIMESTAMP WITHOUT TIME ZONE)
        checked_at = result.checked_at.replace(tzinfo=None) if result.checked_at.tzinfo else result.checked_at

        record = ServiceStatusRecord(
            service_id=service.id,
            status=result.status,
            checked_at=checked_at,
            raw_response=result.raw_response,
        )
        session.add(record)
        await session.flush()

        return record

    async def fetch_incidents(self, service: Service) -> list[ProviderIncident]:
        """Fetch incidents for a service (on-demand).

        Args:
            service: The service to fetch incidents for.

        Returns:
            List of ProviderIncident from the provider.

        Raises:
            ProviderNotFoundError: If service's provider not registered.
            ProviderError: On fetch failure.
        """
        provider = self._registry.get(service.provider)
        return await provider.fetch_incidents(service.status_url)

    async def sync_incidents(
        self,
        session: AsyncSession,
        service: Service,
    ) -> list[Incident]:
        """Fetch and upsert incidents for a service.

        Args:
            session: Database session.
            service: The service to sync incidents for.

        Returns:
            List of created/updated Incident records.
        """
        provider_incidents = await self.fetch_incidents(service)

        results: list[Incident] = []

        for pi in provider_incidents:
            incident = await self._upsert_incident(session, service.id, pi)
            results.append(incident)

        return results

    async def _upsert_incident(
        self,
        session: AsyncSession,
        service_id: UUID,
        pi: ProviderIncident,
    ) -> Incident:
        """Create or update an incident."""
        # Check for existing incident
        stmt = select(Incident).where(
            Incident.service_id == service_id,
            Incident.external_id == pi.external_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.title = pi.title
            existing.description = pi.description
            existing.status = pi.status
            existing.impact = pi.impact
            existing.resolved_at = pi.resolved_at
            return existing
        else:
            # Create new
            incident = Incident(
                service_id=service_id,
                external_id=pi.external_id,
                title=pi.title,
                description=pi.description,
                status=pi.status,
                impact=pi.impact,
                resolved_at=pi.resolved_at,
            )
            session.add(incident)
            await session.flush()
            return incident

    async def sync_all_active_services(
        self,
        session: AsyncSession,
    ) -> dict[UUID, ServiceStatusRecord | ProviderError]:
        """Sync status for all active services.

        Used by background polling task.

        Args:
            session: Database session.

        Returns:
            Dict mapping service_id to result or error.
        """
        stmt = select(Service).where(Service.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        services = result.scalars().all()

        results: dict[UUID, ServiceStatusRecord | ProviderError] = {}

        for service in services:
            try:
                record = await self.sync_status(session, service)
                results[service.id] = record
            except ProviderError as e:
                logger.warning(
                    "Failed to sync %s: %s",
                    service.name,
                    str(e),
                )
                results[service.id] = e

        return results
