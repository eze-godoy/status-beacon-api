"""Status page providers for fetching service health data."""

from src.providers.base import (
    ComponentStatus,
    ProviderIncident,
    ProviderStatusResult,
    StatusProvider,
)
from src.providers.exceptions import (
    ProviderError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderParseError,
    ProviderRateLimitError,
)
from src.providers.registry import (
    ProviderRegistry,
    get_registry,
    init_registry,
    reset_registry,
)

__all__ = [
    # Protocol and data types
    "StatusProvider",
    "ProviderStatusResult",
    "ComponentStatus",
    "ProviderIncident",
    # Registry
    "ProviderRegistry",
    "get_registry",
    "init_registry",
    "reset_registry",
    # Exceptions
    "ProviderError",
    "ProviderNetworkError",
    "ProviderRateLimitError",
    "ProviderParseError",
    "ProviderNotFoundError",
]
