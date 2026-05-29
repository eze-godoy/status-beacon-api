"""Unit tests for Statuspage.io provider."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.models.enums import IncidentImpact, IncidentStatus, ServiceStatus
from src.providers.exceptions import (
    ProviderNetworkError,
    ProviderParseError,
    ProviderRateLimitError,
)
from src.providers.statuspage import StatuspageProvider


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create mock HTTP client."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def provider(mock_http_client: AsyncMock) -> StatuspageProvider:
    """Create Statuspage provider with mock client."""
    return StatuspageProvider(mock_http_client)


def create_mock_response(
    data: dict[str, Any],
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock HTTP response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.headers = headers or {}
    mock.json.return_value = data
    return mock


class TestStatuspageProviderProperties:
    """Tests for provider properties."""

    def test_provider_id(self, provider: StatuspageProvider) -> None:
        """Test provider_id property."""
        assert provider.provider_id == "statuspage"

    def test_provider_name(self, provider: StatuspageProvider) -> None:
        """Test provider_name property."""
        assert provider.provider_name == "Statuspage.io"


class TestFetchStatus:
    """Tests for fetch_status method."""

    async def test_fetch_status_operational(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test fetching operational status."""
        mock_http_client.get.return_value = create_mock_response({
            "status": {"indicator": "none"},
            "components": [
                {
                    "id": "comp1",
                    "name": "API",
                    "status": "operational",
                    "group": False,
                }
            ],
        })

        result = await provider.fetch_status("https://example.statuspage.io")

        assert result.status == ServiceStatus.OPERATIONAL
        assert len(result.components) == 1
        assert result.components[0].name == "API"
        assert result.components[0].status == ServiceStatus.OPERATIONAL

    async def test_fetch_status_major_outage(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test fetching major outage status."""
        mock_http_client.get.return_value = create_mock_response({
            "status": {"indicator": "critical"},
            "components": [],
        })

        result = await provider.fetch_status("https://example.statuspage.io")

        assert result.status == ServiceStatus.MAJOR_OUTAGE

    async def test_fetch_status_degraded(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test fetching degraded status."""
        mock_http_client.get.return_value = create_mock_response({
            "status": {"indicator": "minor"},
            "components": [
                {
                    "id": "comp1",
                    "name": "API",
                    "status": "degraded_performance",
                    "group": False,
                }
            ],
        })

        result = await provider.fetch_status("https://example.statuspage.io")

        assert result.status == ServiceStatus.DEGRADED
        assert result.components[0].status == ServiceStatus.DEGRADED

    async def test_fetch_status_skips_group_components(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that group components are skipped."""
        mock_http_client.get.return_value = create_mock_response({
            "status": {"indicator": "none"},
            "components": [
                {"id": "group1", "name": "Group", "group": True, "status": "operational"},
                {"id": "comp1", "name": "API", "group": False, "status": "operational"},
            ],
        })

        result = await provider.fetch_status("https://example.statuspage.io")

        assert len(result.components) == 1
        assert result.components[0].name == "API"

    async def test_fetch_status_includes_raw_response(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that raw response is included."""
        raw_data = {"status": {"indicator": "none"}, "components": []}
        mock_http_client.get.return_value = create_mock_response(raw_data)

        result = await provider.fetch_status("https://example.statuspage.io")

        assert result.raw_response == raw_data

    async def test_fetch_status_sets_checked_at(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that checked_at is set to current time."""
        mock_http_client.get.return_value = create_mock_response({
            "status": {"indicator": "none"},
            "components": [],
        })

        before = datetime.now(UTC)
        result = await provider.fetch_status("https://example.statuspage.io")
        after = datetime.now(UTC)

        assert before <= result.checked_at <= after

    async def test_fetch_status_normalizes_url(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that trailing slash is removed from URL."""
        mock_http_client.get.return_value = create_mock_response({
            "status": {"indicator": "none"},
            "components": [],
        })

        await provider.fetch_status("https://example.statuspage.io/")

        mock_http_client.get.assert_called_once()
        call_url = mock_http_client.get.call_args[0][0]
        assert call_url == "https://example.statuspage.io/api/v2/summary.json"


class TestFetchStatusErrors:
    """Tests for fetch_status error handling."""

    async def test_fetch_status_rate_limit(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test rate limit handling."""
        mock_http_client.get.return_value = create_mock_response(
            {},
            status_code=429,
            headers={"Retry-After": "60"},
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            await provider.fetch_status("https://example.statuspage.io")

        assert exc_info.value.retry_after == 60
        assert exc_info.value.provider_id == "statuspage"

    async def test_fetch_status_timeout(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test timeout handling."""
        mock_http_client.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(ProviderNetworkError) as exc_info:
            await provider.fetch_status("https://example.statuspage.io")

        assert "Timeout" in str(exc_info.value)
        assert exc_info.value.provider_id == "statuspage"

    async def test_fetch_status_connection_error(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test connection error handling."""
        mock_http_client.get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(ProviderNetworkError) as exc_info:
            await provider.fetch_status("https://example.statuspage.io")

        assert exc_info.value.provider_id == "statuspage"

    async def test_fetch_status_http_error(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test HTTP error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response,
        )

        with pytest.raises(ProviderNetworkError) as exc_info:
            await provider.fetch_status("https://example.statuspage.io")

        assert "500" in str(exc_info.value)

    async def test_fetch_status_invalid_json(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test invalid JSON handling."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_http_client.get.return_value = mock_response

        with pytest.raises(ProviderParseError) as exc_info:
            await provider.fetch_status("https://example.statuspage.io")

        assert exc_info.value.provider_id == "statuspage"


class TestFetchIncidents:
    """Tests for fetch_incidents method."""

    async def test_fetch_incidents_success(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test fetching incidents."""
        mock_http_client.get.return_value = create_mock_response({
            "incidents": [
                {
                    "id": "inc1",
                    "name": "API Latency",
                    "status": "investigating",
                    "impact": "minor",
                    "started_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-01T10:30:00Z",
                    "resolved_at": None,
                    "incident_updates": [{"body": "Investigating increased latency"}],
                }
            ]
        })

        result = await provider.fetch_incidents("https://example.statuspage.io")

        assert len(result) == 1
        assert result[0].external_id == "inc1"
        assert result[0].title == "API Latency"
        assert result[0].status == IncidentStatus.INVESTIGATING
        assert result[0].impact == IncidentImpact.MINOR
        assert result[0].description == "Investigating increased latency"

    async def test_fetch_incidents_empty(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test fetching with no incidents."""
        mock_http_client.get.return_value = create_mock_response({"incidents": []})

        result = await provider.fetch_incidents("https://example.statuspage.io")

        assert result == []

    async def test_fetch_incidents_resolved(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test fetching resolved incident."""
        mock_http_client.get.return_value = create_mock_response({
            "incidents": [
                {
                    "id": "inc1",
                    "name": "Issue Fixed",
                    "status": "resolved",
                    "impact": "major",
                    "started_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-01T12:00:00Z",
                    "resolved_at": "2024-01-01T12:00:00Z",
                    "incident_updates": [],
                }
            ]
        })

        result = await provider.fetch_incidents("https://example.statuspage.io")

        assert result[0].status == IncidentStatus.RESOLVED
        assert result[0].resolved_at is not None

    async def test_fetch_incidents_skips_invalid(
        self,
        provider: StatuspageProvider,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that invalid incidents are skipped."""
        mock_http_client.get.return_value = create_mock_response({
            "incidents": [
                {"id": "invalid"},  # Missing required fields
                {
                    "id": "valid",
                    "name": "Valid Incident",
                    "status": "investigating",
                    "impact": "minor",
                    "started_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-01T10:30:00Z",
                    "incident_updates": [],
                },
            ]
        })

        result = await provider.fetch_incidents("https://example.statuspage.io")

        assert len(result) == 1
        assert result[0].external_id == "valid"


class TestStatusMapping:
    """Tests for status value mapping."""

    @pytest.mark.parametrize(
        ("statuspage_status", "expected"),
        [
            ("operational", ServiceStatus.OPERATIONAL),
            ("degraded_performance", ServiceStatus.DEGRADED),
            ("partial_outage", ServiceStatus.PARTIAL_OUTAGE),
            ("major_outage", ServiceStatus.MAJOR_OUTAGE),
            ("under_maintenance", ServiceStatus.MAINTENANCE),
        ],
    )
    def test_component_status_mapping(
        self,
        provider: StatuspageProvider,
        statuspage_status: str,
        expected: ServiceStatus,
    ) -> None:
        """Test component status mapping."""
        result = provider.STATUS_MAP.get(statuspage_status, ServiceStatus.UNKNOWN)
        assert result == expected

    def test_unknown_status_maps_to_unknown(
        self,
        provider: StatuspageProvider,
    ) -> None:
        """Test that unknown status maps to UNKNOWN."""
        result = provider.STATUS_MAP.get("some_new_status", ServiceStatus.UNKNOWN)
        assert result == ServiceStatus.UNKNOWN

    @pytest.mark.parametrize(
        ("indicator", "expected"),
        [
            ("none", ServiceStatus.OPERATIONAL),
            ("minor", ServiceStatus.DEGRADED),
            ("major", ServiceStatus.PARTIAL_OUTAGE),
            ("critical", ServiceStatus.MAJOR_OUTAGE),
            ("maintenance", ServiceStatus.MAINTENANCE),
        ],
    )
    def test_page_indicator_mapping(
        self,
        provider: StatuspageProvider,
        indicator: str,
        expected: ServiceStatus,
    ) -> None:
        """Test page-level status indicator mapping."""
        result = provider.INDICATOR_MAP.get(indicator, ServiceStatus.UNKNOWN)
        assert result == expected


class TestIncidentMapping:
    """Tests for incident status and impact mapping."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("investigating", IncidentStatus.INVESTIGATING),
            ("identified", IncidentStatus.IDENTIFIED),
            ("monitoring", IncidentStatus.MONITORING),
            ("resolved", IncidentStatus.RESOLVED),
            ("postmortem", IncidentStatus.POSTMORTEM),
        ],
    )
    def test_incident_status_mapping(
        self,
        provider: StatuspageProvider,
        status: str,
        expected: IncidentStatus,
    ) -> None:
        """Test incident status mapping."""
        result = provider.INCIDENT_STATUS_MAP.get(status, IncidentStatus.INVESTIGATING)
        assert result == expected

    @pytest.mark.parametrize(
        ("impact", "expected"),
        [
            ("none", IncidentImpact.NONE),
            ("minor", IncidentImpact.MINOR),
            ("major", IncidentImpact.MAJOR),
            ("critical", IncidentImpact.CRITICAL),
        ],
    )
    def test_incident_impact_mapping(
        self,
        provider: StatuspageProvider,
        impact: str,
        expected: IncidentImpact,
    ) -> None:
        """Test incident impact mapping."""
        result = provider.IMPACT_MAP.get(impact, IncidentImpact.NONE)
        assert result == expected
