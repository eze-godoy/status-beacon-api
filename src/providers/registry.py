"""Simple dictionary-based provider registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.providers.base import StatusProvider
from src.providers.exceptions import ProviderNotFoundError

if TYPE_CHECKING:
    import httpx


class ProviderRegistry:
    """Registry for status page providers.

    Simple dict-based registry with manual registration.
    Thread-safe for read operations (dict is atomic).
    """

    def __init__(self) -> None:
        self._providers: dict[str, StatusProvider] = {}

    def register(self, provider: StatusProvider) -> None:
        """Register a provider instance.

        Args:
            provider: Provider instance implementing StatusProvider protocol.
        """
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> StatusProvider:
        """Get a provider by ID.

        Args:
            provider_id: The unique provider identifier.

        Returns:
            The registered provider instance.

        Raises:
            ProviderNotFoundError: If provider not registered.
        """
        if provider_id not in self._providers:
            raise ProviderNotFoundError(provider_id)
        return self._providers[provider_id]

    def get_or_none(self, provider_id: str) -> StatusProvider | None:
        """Get a provider by ID, returning None if not found."""
        return self._providers.get(provider_id)

    def list_providers(self) -> list[str]:
        """List all registered provider IDs."""
        return list(self._providers.keys())

    def is_registered(self, provider_id: str) -> bool:
        """Check if a provider is registered."""
        return provider_id in self._providers


# Global registry instance
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """Get or create the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry. Useful for testing."""
    global _registry
    _registry = None


def init_registry(http_client: httpx.AsyncClient) -> ProviderRegistry:
    """Initialize registry with all providers.

    Called during application startup.

    Args:
        http_client: Configured async HTTP client for providers to use.

    Returns:
        The initialized provider registry.
    """
    from src.providers.statuspage import StatuspageProvider

    registry = get_registry()

    # Register providers
    registry.register(StatuspageProvider(http_client))

    return registry
