"""Statuspage.io provider implementation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from src.models.enums import IncidentImpact, IncidentStatus, ServiceStatus
from src.providers.base import (
    ComponentStatus,
    ProviderIncident,
    ProviderStatusResult,
)
from src.providers.exceptions import (
    ProviderNetworkError,
    ProviderParseError,
    ProviderRateLimitError,
)


class StatuspageProvider:
    """Provider for Atlassian Statuspage.io-based status pages.

    Supports services like Cloudflare, GitHub, Twilio, Stripe, Datadog, etc.

    Rate limit: 1 request/second (enforced with asyncio.Lock).
    """

    SUMMARY_ENDPOINT = "/api/v2/summary.json"
    INCIDENTS_ENDPOINT = "/api/v2/incidents.json"

    # Statuspage.io component status -> our ServiceStatus mapping
    STATUS_MAP: dict[str, ServiceStatus] = {
        "operational": ServiceStatus.OPERATIONAL,
        "degraded_performance": ServiceStatus.DEGRADED,
        "partial_outage": ServiceStatus.PARTIAL_OUTAGE,
        "major_outage": ServiceStatus.MAJOR_OUTAGE,
        "under_maintenance": ServiceStatus.MAINTENANCE,
    }

    # Statuspage.io page indicator -> our ServiceStatus mapping
    INDICATOR_MAP: dict[str, ServiceStatus] = {
        "none": ServiceStatus.OPERATIONAL,
        "minor": ServiceStatus.DEGRADED,
        "major": ServiceStatus.PARTIAL_OUTAGE,
        "critical": ServiceStatus.MAJOR_OUTAGE,
        "maintenance": ServiceStatus.MAINTENANCE,
    }

    # Statuspage.io incident status -> our IncidentStatus mapping
    INCIDENT_STATUS_MAP: dict[str, IncidentStatus] = {
        "investigating": IncidentStatus.INVESTIGATING,
        "identified": IncidentStatus.IDENTIFIED,
        "monitoring": IncidentStatus.MONITORING,
        "resolved": IncidentStatus.RESOLVED,
        "postmortem": IncidentStatus.POSTMORTEM,
    }

    # Statuspage.io impact -> our IncidentImpact mapping
    IMPACT_MAP: dict[str, IncidentImpact] = {
        "none": IncidentImpact.NONE,
        "minor": IncidentImpact.MINOR,
        "major": IncidentImpact.MAJOR,
        "critical": IncidentImpact.CRITICAL,
    }

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """Initialize with shared HTTP client.

        Args:
            http_client: Configured async HTTP client.
        """
        self._client = http_client
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider type."""
        return "statuspage"

    @property
    def provider_name(self) -> str:
        """Human-readable name."""
        return "Statuspage.io"

    async def _rate_limited_get(self, url: str) -> httpx.Response:
        """Execute GET request with rate limiting (1 req/sec)."""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

            self._last_request_time = asyncio.get_event_loop().time()

            try:
                response = await self._client.get(url)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise ProviderRateLimitError(
                        f"Rate limit exceeded for {url}",
                        self.provider_id,
                        retry_after=int(retry_after) if retry_after else None,
                    )

                response.raise_for_status()
                return response

            except httpx.TimeoutException as e:
                raise ProviderNetworkError(
                    f"Timeout fetching {url}",
                    self.provider_id,
                    cause=e,
                ) from e
            except httpx.HTTPStatusError as e:
                raise ProviderNetworkError(
                    f"HTTP error {e.response.status_code} for {url}",
                    self.provider_id,
                    cause=e,
                ) from e
            except httpx.RequestError as e:
                raise ProviderNetworkError(
                    f"Network error fetching {url}",
                    self.provider_id,
                    cause=e,
                ) from e

    def _normalize_base_url(self, status_url: str) -> str:
        """Ensure URL ends without trailing slash."""
        return status_url.rstrip("/")

    async def fetch_status(self, status_url: str) -> ProviderStatusResult:
        """Fetch summary status from Statuspage.io."""
        base_url = self._normalize_base_url(status_url)
        url = f"{base_url}{self.SUMMARY_ENDPOINT}"

        response = await self._rate_limited_get(url)

        try:
            data = response.json()
        except Exception as e:
            raise ProviderParseError(
                f"Failed to parse JSON from {url}",
                self.provider_id,
                cause=e,
            ) from e

        return self._parse_summary(data)

    def _parse_summary(self, data: dict[str, Any]) -> ProviderStatusResult:
        """Parse summary.json response."""
        try:
            # Overall page status indicator
            page_indicator = data.get("status", {}).get("indicator", "none")
            overall_status = self.INDICATOR_MAP.get(page_indicator, ServiceStatus.UNKNOWN)

            # Parse components
            components: list[ComponentStatus] = []
            for comp in data.get("components", []):
                # Skip group headers (they have group=True)
                if comp.get("group"):
                    continue

                comp_status = self.STATUS_MAP.get(
                    comp.get("status", ""),
                    ServiceStatus.UNKNOWN,
                )
                components.append(
                    ComponentStatus(
                        id=comp["id"],
                        name=comp["name"],
                        status=comp_status,
                        description=comp.get("description"),
                        group_id=comp.get("group_id"),
                    )
                )

            return ProviderStatusResult(
                status=overall_status,
                checked_at=datetime.now(UTC),
                raw_response=data,
                components=components,
            )

        except KeyError as e:
            raise ProviderParseError(
                f"Missing required field: {e}",
                self.provider_id,
                cause=e,
            ) from e

    async def fetch_incidents(self, status_url: str) -> list[ProviderIncident]:
        """Fetch incidents from Statuspage.io."""
        base_url = self._normalize_base_url(status_url)
        url = f"{base_url}{self.INCIDENTS_ENDPOINT}"

        response = await self._rate_limited_get(url)

        try:
            data = response.json()
        except Exception as e:
            raise ProviderParseError(
                f"Failed to parse JSON from {url}",
                self.provider_id,
                cause=e,
            ) from e

        return self._parse_incidents(data)

    def _parse_incidents(self, data: dict[str, Any]) -> list[ProviderIncident]:
        """Parse incidents.json response."""
        incidents: list[ProviderIncident] = []

        for incident_data in data.get("incidents", []):
            try:
                incident = self._parse_single_incident(incident_data)
                incidents.append(incident)
            except (KeyError, ValueError):
                # Log warning but continue with other incidents
                continue

        return incidents

    def _parse_single_incident(self, data: dict[str, Any]) -> ProviderIncident:
        """Parse a single incident."""
        status_str = data.get("status", "investigating")
        status = self.INCIDENT_STATUS_MAP.get(status_str, IncidentStatus.INVESTIGATING)

        impact_str = data.get("impact", "none")
        impact = self.IMPACT_MAP.get(impact_str, IncidentImpact.NONE)

        # Build description from latest update
        updates = data.get("incident_updates", [])
        description = updates[0].get("body") if updates else None

        return ProviderIncident(
            external_id=data["id"],
            title=data["name"],
            description=description,
            status=status,
            impact=impact,
            started_at=self._parse_datetime(data["started_at"]),
            resolved_at=self._parse_datetime(data.get("resolved_at")),
            updated_at=self._parse_datetime(data["updated_at"]),
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO 8601 datetime string."""
        if value is None:
            return None
        # Handle both 'Z' and '+00:00' suffixes
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
