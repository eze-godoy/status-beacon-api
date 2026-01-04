"""Health check endpoints."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

from src import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy"]
    version: str


class ReadinessResponse(BaseModel):
    """Detailed health check with component status."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    database: Literal["connected", "disconnected"]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the API",
)
async def health_check() -> HealthResponse:
    """Check if the API is healthy."""
    return HealthResponse(status="healthy", version=__version__)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    description="Returns detailed health status including database connectivity",
)
async def readiness_check(request: Request) -> ReadinessResponse:
    """Check if the API is ready to serve requests.

    This endpoint verifies database connectivity in addition to basic health.
    """
    db_status: Literal["connected", "disconnected"] = "disconnected"

    try:
        session_factory = request.app.state.db_session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:  # noqa: S110  # nosec B110
        pass

    overall_status: Literal["healthy", "degraded", "unhealthy"] = (
        "healthy" if db_status == "connected" else "unhealthy"
    )

    return ReadinessResponse(
        status=overall_status,
        version=__version__,
        database=db_status,
    )
