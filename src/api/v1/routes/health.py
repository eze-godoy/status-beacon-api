"""Health check endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from src import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy"]
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the API",
)
async def health_check() -> HealthResponse:
    """Check if the API is healthy."""
    return HealthResponse(status="healthy", version=__version__)
