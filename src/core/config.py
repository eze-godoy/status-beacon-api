"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required env vars (no defaults - must be set):
        - POSTGRES_USER
        - POSTGRES_PASSWORD
        - POSTGRES_HOST
        - POSTGRES_DB

    Optional env vars (have sensible defaults):
        - APP_NAME, DEBUG, ENVIRONMENT
        - HOST, PORT
        - POSTGRES_PORT, DB_POOL_SIZE, DB_POOL_OVERFLOW, DB_POOL_TIMEOUT
        - CORS_ORIGINS
        - RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
        - STATUS_POLL_INTERVAL_SECONDS
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Status Beacon API"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_v1_prefix: str = "/api/v1"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Database - REQUIRED (no defaults for sensitive/environment-specific values)
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str
    postgres_db: str
    postgres_port: int = 5432

    # Database connection pool settings
    db_pool_size: int = 5  # Number of connections to keep open
    db_pool_overflow: int = 10  # Max extra connections when pool is exhausted
    db_pool_timeout: int = 30  # Seconds to wait for a connection from pool

    @property
    def database_url(self) -> PostgresDsn:
        """Build the database URL from components.

        Note: This is a regular property (not computed_field) to prevent
        the URL with password from being included in serialization/logging.
        """
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )

    @property
    def database_url_masked(self) -> str:
        """Return database URL with password masked for logging."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:***@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # CORS (sensible defaults for local dev)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:7007"]

    # Rate limiting
    rate_limit_requests: int = 100  # Max requests per window
    rate_limit_window_seconds: int = 60  # Window duration in seconds

    # Polling (operational default)
    status_poll_interval_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
