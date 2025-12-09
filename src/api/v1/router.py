"""API v1 router aggregating all route modules."""

from fastapi import APIRouter

from src.api.v1.routes import health

api_router = APIRouter()

api_router.include_router(health.router)
