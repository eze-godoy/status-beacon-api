"""Service status API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from src.api.dependencies import DbSession
from src.models.enums import IncidentStatus
from src.models.incident import Incident
from src.models.service import Service
from src.models.service_status import ServiceStatusRecord
from src.providers.exceptions import ProviderError, ProviderNotFoundError
from src.schemas.service import (
    IncidentResponse,
    ServiceCreate,
    ServiceResponse,
    ServiceStatusDetailResponse,
    ServiceUpdate,
    StatusResponse,
    SyncResultResponse,
)

router = APIRouter(prefix="/services", tags=["services"])


# --- List and Create ---


@router.get("", response_model=list[ServiceResponse])
async def list_services(
    session: DbSession,
    active_only: bool = True,
) -> list[Service]:
    """List all monitored services.

    Args:
        session: Database session.
        active_only: If True, only return active services.

    Returns:
        List of services.
    """
    stmt = select(Service)
    if active_only:
        stmt = stmt.where(Service.is_active == True)  # noqa: E712

    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    service_data: ServiceCreate,
    session: DbSession,
    request: Request,
) -> Service:
    """Create a new service to monitor.

    Args:
        service_data: Service creation data.
        session: Database session.
        request: FastAPI request.

    Returns:
        Created service.

    Raises:
        HTTPException: If provider not found or service name already exists.
    """
    # Validate provider exists
    registry = request.app.state.provider_registry
    if not registry.is_registered(service_data.provider):
        available = registry.list_providers()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{service_data.provider}' not found. Available: {available}",
        )

    # Check for duplicate name
    stmt = select(Service).where(Service.name == service_data.name)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service with name '{service_data.name}' already exists",
        )

    service = Service(
        name=service_data.name,
        provider=service_data.provider,
        status_url=str(service_data.status_url),
        is_active=service_data.is_active,
        poll_interval_seconds=service_data.poll_interval_seconds,
    )
    session.add(service)
    await session.flush()

    return service


# --- Get, Update, Delete ---


@router.get("/{service_id}", response_model=ServiceStatusDetailResponse)
async def get_service_status(
    service_id: UUID,
    session: DbSession,
    request: Request,
) -> dict:
    """Get current status for a service (on-demand fetch).

    Args:
        service_id: Service UUID.
        session: Database session.
        request: FastAPI request.

    Returns:
        Service details with current status and active incidents.

    Raises:
        HTTPException: If service not found or provider error.
    """
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )

    sync_service = request.app.state.status_sync_service

    current_status = None
    try:
        # Use sync_status which handles timezone conversion
        record = await sync_service.sync_status(session, service)

        current_status = StatusResponse(
            status=record.status,
            checked_at=record.checked_at,
            service_id=service.id,
            service_name=service.name,
        )
    except ProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{service.provider}' not configured",
        )
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch status: {e}",
        )

    # Get active incidents
    active_incidents = [
        IncidentResponse.model_validate(inc)
        for inc in service.incidents
        if inc.status != IncidentStatus.RESOLVED
    ]

    return {
        "service": service,
        "current_status": current_status,
        "active_incidents": active_incidents,
    }


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: UUID,
    service_data: ServiceUpdate,
    session: DbSession,
) -> Service:
    """Update service configuration.

    Args:
        service_id: Service UUID.
        service_data: Fields to update.
        session: Database session.

    Returns:
        Updated service.

    Raises:
        HTTPException: If service not found or name conflict.
    """
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )

    # Check for name conflict if name is being updated
    if service_data.name and service_data.name != service.name:
        stmt = select(Service).where(Service.name == service_data.name)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Service with name '{service_data.name}' already exists",
            )

    # Update fields
    update_data = service_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status_url" and value is not None:
            value = str(value)
        setattr(service, field, value)

    await session.flush()
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID,
    session: DbSession,
) -> None:
    """Delete a service.

    Args:
        service_id: Service UUID.
        session: Database session.

    Raises:
        HTTPException: If service not found.
    """
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )

    await session.delete(service)


# --- Sync Operations ---


@router.post("/{service_id}/sync", response_model=StatusResponse)
async def sync_service_status(
    service_id: UUID,
    session: DbSession,
    request: Request,
) -> dict:
    """Manually trigger status sync for a service.

    Args:
        service_id: Service UUID.
        session: Database session.
        request: FastAPI request.

    Returns:
        Synced status.

    Raises:
        HTTPException: If service not found or provider error.
    """
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )

    sync_service = request.app.state.status_sync_service

    try:
        record = await sync_service.sync_status(session, service)
        return {
            "status": record.status,
            "checked_at": record.checked_at,
            "service_id": service.id,
            "service_name": service.name,
        }
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.post("/{service_id}/sync-incidents", response_model=SyncResultResponse)
async def sync_service_incidents(
    service_id: UUID,
    session: DbSession,
    request: Request,
) -> dict:
    """Manually sync incidents for a service.

    Args:
        service_id: Service UUID.
        session: Database session.
        request: FastAPI request.

    Returns:
        Sync result with count.

    Raises:
        HTTPException: If service not found or provider error.
    """
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )

    sync_service = request.app.state.status_sync_service

    try:
        incidents = await sync_service.sync_incidents(session, service)
        return {
            "synced_count": len(incidents),
            "service_id": service_id,
        }
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


# --- Provider Info ---


@router.get("/providers/list", response_model=list[str])
async def list_providers(request: Request) -> list[str]:
    """List available provider types.

    Args:
        request: FastAPI request.

    Returns:
        List of registered provider IDs.
    """
    registry = request.app.state.provider_registry
    return registry.list_providers()
