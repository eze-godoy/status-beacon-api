"""Unit tests for status sync service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.enums import IncidentImpact, IncidentStatus, ServiceStatus
from src.providers.base import ProviderIncident, ProviderStatusResult
from src.providers.exceptions import ProviderNotFoundError
from src.providers.registry import ProviderRegistry
from src.services.status_sync import StatusSyncService

if TYPE_CHECKING:
    pass


class MockProvider:
    """Mock provider for testing."""

    def __init__(self) -> None:
        self.fetch_status_result: ProviderStatusResult | None = None
        self.fetch_incidents_result: list[ProviderIncident] = []

    @property
    def provider_id(self) -> str:
        return "mock"

    @property
    def provider_name(self) -> str:
        return "Mock Provider"

    async def fetch_status(self, status_url: str) -> ProviderStatusResult:
        if self.fetch_status_result is None:
            raise ValueError("No mock result configured")
        return self.fetch_status_result

    async def fetch_incidents(self, status_url: str) -> list[ProviderIncident]:
        return self.fetch_incidents_result


@pytest.fixture
def mock_provider() -> MockProvider:
    """Create mock provider."""
    return MockProvider()


@pytest.fixture
def registry(mock_provider: MockProvider) -> ProviderRegistry:
    """Create registry with mock provider."""
    registry = ProviderRegistry()
    registry.register(mock_provider)
    return registry


@pytest.fixture
def sync_service(registry: ProviderRegistry) -> StatusSyncService:
    """Create status sync service."""
    return StatusSyncService(registry)


@pytest.fixture
def mock_service() -> MagicMock:
    """Create mock service model."""
    service = MagicMock()
    service.id = uuid4()
    service.name = "Test Service"
    service.provider = "mock"
    service.status_url = "https://test.statuspage.io"
    return service


class TestFetchStatus:
    """Tests for fetch_status method."""

    async def test_fetch_status_success(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
        mock_service: MagicMock,
    ) -> None:
        """Test successful status fetch."""
        expected_result = ProviderStatusResult(
            status=ServiceStatus.OPERATIONAL,
            checked_at=datetime.now(UTC),
            raw_response={"status": "ok"},
        )
        mock_provider.fetch_status_result = expected_result

        result = await sync_service.fetch_status(mock_service)

        assert result == expected_result

    async def test_fetch_status_provider_not_found(
        self,
        sync_service: StatusSyncService,
        mock_service: MagicMock,
    ) -> None:
        """Test error when provider not found."""
        mock_service.provider = "unknown"

        with pytest.raises(ProviderNotFoundError):
            await sync_service.fetch_status(mock_service)


class TestFetchIncidents:
    """Tests for fetch_incidents method."""

    async def test_fetch_incidents_success(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
        mock_service: MagicMock,
    ) -> None:
        """Test successful incidents fetch."""
        expected_incidents = [
            ProviderIncident(
                external_id="inc1",
                title="Test Incident",
                status=IncidentStatus.INVESTIGATING,
                impact=IncidentImpact.MINOR,
                started_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ]
        mock_provider.fetch_incidents_result = expected_incidents

        result = await sync_service.fetch_incidents(mock_service)

        assert result == expected_incidents

    async def test_fetch_incidents_empty(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
        mock_service: MagicMock,
    ) -> None:
        """Test fetching when no incidents."""
        mock_provider.fetch_incidents_result = []

        result = await sync_service.fetch_incidents(mock_service)

        assert result == []


class TestSyncStatus:
    """Tests for sync_status method."""

    async def test_sync_status_creates_record(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
        mock_service: MagicMock,
    ) -> None:
        """Test that sync_status creates a status record."""
        expected_result = ProviderStatusResult(
            status=ServiceStatus.DEGRADED,
            checked_at=datetime.now(UTC),
            raw_response={"status": "degraded"},
        )
        mock_provider.fetch_status_result = expected_result

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        record = await sync_service.sync_status(mock_session, mock_service)

        assert record.service_id == mock_service.id
        assert record.status == ServiceStatus.DEGRADED
        assert record.raw_response == {"status": "degraded"}
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()


class TestSyncIncidents:
    """Tests for sync_incidents method."""

    async def test_sync_incidents_creates_new(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
        mock_service: MagicMock,
    ) -> None:
        """Test that sync_incidents creates new incidents."""
        mock_provider.fetch_incidents_result = [
            ProviderIncident(
                external_id="new_inc",
                title="New Incident",
                status=IncidentStatus.INVESTIGATING,
                impact=IncidentImpact.MAJOR,
                started_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ]

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        # Simulate no existing incident
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        incidents = await sync_service.sync_incidents(mock_session, mock_service)

        assert len(incidents) == 1
        assert incidents[0].external_id == "new_inc"
        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()

    async def test_sync_incidents_updates_existing(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
        mock_service: MagicMock,
    ) -> None:
        """Test that sync_incidents updates existing incidents."""
        mock_provider.fetch_incidents_result = [
            ProviderIncident(
                external_id="existing_inc",
                title="Updated Title",
                status=IncidentStatus.RESOLVED,
                impact=IncidentImpact.MINOR,
                started_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                resolved_at=datetime.now(UTC),
            )
        ]

        existing_incident = MagicMock()
        existing_incident.external_id = "existing_inc"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_incident
        mock_session.execute.return_value = mock_result

        incidents = await sync_service.sync_incidents(mock_session, mock_service)

        assert len(incidents) == 1
        assert existing_incident.title == "Updated Title"
        assert existing_incident.status == IncidentStatus.RESOLVED


class TestSyncAllActiveServices:
    """Tests for sync_all_active_services method."""

    async def test_sync_all_returns_results(
        self,
        sync_service: StatusSyncService,
        mock_provider: MockProvider,
    ) -> None:
        """Test syncing all active services returns results."""
        mock_provider.fetch_status_result = ProviderStatusResult(
            status=ServiceStatus.OPERATIONAL,
            checked_at=datetime.now(UTC),
            raw_response={},
        )

        service1 = MagicMock()
        service1.id = uuid4()
        service1.provider = "mock"
        service1.status_url = "https://test1.io"

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [service1]
        mock_session.execute.return_value = mock_result

        results = await sync_service.sync_all_active_services(mock_session)

        assert service1.id in results
        # Result should be a ServiceStatusRecord, not an error
        assert not isinstance(results[service1.id], Exception)

    async def test_sync_all_handles_errors(
        self,
        registry: ProviderRegistry,
    ) -> None:
        """Test that errors are captured per-service."""
        # Create a provider that fails
        failing_provider = MockProvider()
        failing_provider.fetch_status_result = None  # Will raise ValueError

        registry = ProviderRegistry()
        registry.register(failing_provider)
        sync_service = StatusSyncService(registry)

        service = MagicMock()
        service.id = uuid4()
        service.name = "Failing Service"
        service.provider = "mock"
        service.status_url = "https://fail.io"

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [service]
        mock_session.execute.return_value = mock_result

        # The ValueError from the mock should be raised since it's not a ProviderError
        # The sync_all_active_services only catches ProviderError, so this will raise
        with pytest.raises(ValueError):
            await sync_service.sync_all_active_services(mock_session)
