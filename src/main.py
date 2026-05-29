"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response

from src import __version__
from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.database import create_engine, create_session_factory
from src.core.http_client import create_http_client
from src.providers.registry import init_registry
from src.services.status_sync import StatusSyncService
from src.tasks.background import BackgroundPoller

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(
    request: Request,  # noqa: ARG001
    exc: Exception,  # noqa: ARG001
) -> Response:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    settings = get_settings()
    app.state.settings = settings

    # Initialize database
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # Initialize HTTP client for providers
    http_client = create_http_client(settings)
    app.state.http_client = http_client

    # Initialize provider registry
    registry = init_registry(http_client)
    app.state.provider_registry = registry

    # Initialize status sync service
    sync_service = StatusSyncService(registry)
    app.state.status_sync_service = sync_service

    # Start background poller
    poller = BackgroundPoller(sync_service, session_factory, settings)
    app.state.background_poller = poller
    await poller.start()

    yield

    # Shutdown
    await poller.stop()
    await http_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory for creating the FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Cloud status aggregator API with Backstage integration "
            "for monitoring third-party service health"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check endpoints for monitoring API status",
            },
            {
                "name": "services",
                "description": "Service status management and monitoring endpoints",
            },
        ],
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Include API router
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
