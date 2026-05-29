"""Pydantic schemas for service-related API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.models.enums import IncidentImpact, IncidentStatus, ServiceStatus


class ServiceCreate(BaseModel):
    """Schema for creating a new service."""

    name: str = Field(..., min_length=1, max_length=100, description="Service name")
    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Provider ID (e.g., 'statuspage')",
    )
    status_url: HttpUrl = Field(..., description="Base URL of the status page")
    is_active: bool = Field(default=True, description="Whether to actively monitor")
    poll_interval_seconds: int | None = Field(
        default=None,
        ge=10,
        le=3600,
        description="Custom polling interval (10-3600 seconds). Uses global default if not set.",
    )


class ServiceUpdate(BaseModel):
    """Schema for updating an existing service."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Service name",
    )
    status_url: HttpUrl | None = Field(
        default=None,
        description="Base URL of the status page",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether to actively monitor",
    )
    poll_interval_seconds: int | None = Field(
        default=None,
        ge=10,
        le=3600,
        description="Custom polling interval (10-3600 seconds)",
    )


class ServiceResponse(BaseModel):
    """Schema for service response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider: str
    status_url: str
    is_active: bool
    poll_interval_seconds: int | None
    created_at: datetime
    updated_at: datetime


class StatusResponse(BaseModel):
    """Schema for current service status."""

    status: ServiceStatus
    checked_at: datetime
    service_id: UUID
    service_name: str


class IncidentResponse(BaseModel):
    """Schema for incident details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    title: str
    description: str | None
    status: IncidentStatus
    impact: IncidentImpact
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ServiceStatusDetailResponse(BaseModel):
    """Schema for combined service status with recent incidents."""

    service: ServiceResponse
    current_status: StatusResponse | None
    active_incidents: list[IncidentResponse]


class SyncResultResponse(BaseModel):
    """Schema for sync operation result."""

    synced_count: int
    service_id: UUID
