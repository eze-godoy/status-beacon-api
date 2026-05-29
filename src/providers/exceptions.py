"""Provider-specific exceptions."""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(
        self,
        message: str,
        provider_id: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.cause = cause


class ProviderNetworkError(ProviderError):
    """Network-related errors (connection, timeout)."""

    pass


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str,
        provider_id: str,
        retry_after: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, provider_id, cause)
        self.retry_after = retry_after


class ProviderParseError(ProviderError):
    """Failed to parse provider response."""

    pass


class ProviderNotFoundError(Exception):
    """Provider not found in registry."""

    def __init__(self, provider_id: str) -> None:
        super().__init__(f"Provider '{provider_id}' not found in registry")
        self.provider_id = provider_id
