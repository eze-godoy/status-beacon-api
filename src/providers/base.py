"""Base provider protocol and types for status page integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.models.enums import IncidentImpact, IncidentStatus, ServiceStatus


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    """Status of an individual component within a service."""

    id: str
    name: str
    status: ServiceStatus
    description: str | None = None
    group_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderStatusResult:
    """Result from fetching service status."""

    status: ServiceStatus
    checked_at: datetime
    raw_response: dict[str, Any]
    components: list[ComponentStatus] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProviderIncident:
    """Incident data from a provider."""

    external_id: str
    title: str
    status: IncidentStatus
    impact: IncidentImpact
    started_at: datetime
    updated_at: datetime
    description: str | None = None
    resolved_at: datetime | None = None


@runtime_checkable
class StatusProvider(Protocol):
    """Protocol for status page providers.

    All providers must implement this interface to be registered
    with the provider registry.
    """

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider type (e.g., 'statuspage')."""
        ...

    @property
    def provider_name(self) -> str:
        """Human-readable name (e.g., 'Statuspage.io')."""
        ...

    async def fetch_status(self, status_url: str) -> ProviderStatusResult:
        """Fetch current status from the service's status page.

        Args:
            status_url: Base URL of the status page.

        Returns:
            ProviderStatusResult with current status and raw data.

        Raises:
            ProviderError: On network or parsing errors.
        """
        ...

    async def fetch_incidents(self, status_url: str) -> list[ProviderIncident]:
        """Fetch active and recent incidents.

        Args:
            status_url: Base URL of the status page.

        Returns:
            List of incidents (unresolved + recently resolved).

        Raises:
            ProviderError: On network or parsing errors.
        """
        ...
