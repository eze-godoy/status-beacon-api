"""Tests for provider registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.providers.base import ProviderIncident, ProviderStatusResult
from src.providers.exceptions import ProviderNotFoundError
from src.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    pass


class MockProvider:
    """Mock provider for testing."""

    def __init__(self, provider_id: str = "mock") -> None:
        self._provider_id = provider_id

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_name(self) -> str:
        return "Mock Provider"

    async def fetch_status(self, status_url: str) -> ProviderStatusResult:
        raise NotImplementedError

    async def fetch_incidents(self, status_url: str) -> list[ProviderIncident]:
        raise NotImplementedError


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_register_and_get(self) -> None:
        """Test registering and retrieving a provider."""
        registry = ProviderRegistry()
        provider = MockProvider()

        registry.register(provider)
        result = registry.get("mock")

        assert result is provider

    def test_get_not_found(self) -> None:
        """Test getting non-existent provider raises error."""
        registry = ProviderRegistry()

        with pytest.raises(ProviderNotFoundError) as exc_info:
            registry.get("nonexistent")

        assert exc_info.value.provider_id == "nonexistent"

    def test_get_or_none_found(self) -> None:
        """Test get_or_none returns provider when found."""
        registry = ProviderRegistry()
        provider = MockProvider()
        registry.register(provider)

        result = registry.get_or_none("mock")

        assert result is provider

    def test_get_or_none_not_found(self) -> None:
        """Test get_or_none returns None when not found."""
        registry = ProviderRegistry()

        result = registry.get_or_none("nonexistent")

        assert result is None

    def test_list_providers_empty(self) -> None:
        """Test listing providers on empty registry."""
        registry = ProviderRegistry()

        result = registry.list_providers()

        assert result == []

    def test_list_providers(self) -> None:
        """Test listing registered providers."""
        registry = ProviderRegistry()
        registry.register(MockProvider("provider1"))
        registry.register(MockProvider("provider2"))

        result = registry.list_providers()

        assert sorted(result) == ["provider1", "provider2"]

    def test_is_registered_true(self) -> None:
        """Test is_registered returns True for registered provider."""
        registry = ProviderRegistry()
        registry.register(MockProvider())

        assert registry.is_registered("mock") is True

    def test_is_registered_false(self) -> None:
        """Test is_registered returns False for unregistered provider."""
        registry = ProviderRegistry()

        assert registry.is_registered("nonexistent") is False

    def test_register_overwrites(self) -> None:
        """Test registering same provider_id overwrites previous."""
        registry = ProviderRegistry()
        provider1 = MockProvider()
        provider2 = MockProvider()

        registry.register(provider1)
        registry.register(provider2)

        result = registry.get("mock")
        assert result is provider2
