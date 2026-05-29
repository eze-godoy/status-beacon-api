"""Shared HTTP client configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from src.core.config import Settings


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    """Create configured async HTTP client.

    Args:
        settings: Application settings.

    Returns:
        Configured httpx.AsyncClient for making async HTTP requests.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.provider_request_timeout,
            connect=settings.provider_connect_timeout,
        ),
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
        ),
        headers={
            "User-Agent": f"StatusBeacon/1.0 ({settings.app_name})",
            "Accept": "application/json",
        },
        follow_redirects=True,
    )
