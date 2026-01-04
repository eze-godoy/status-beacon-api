"""Enum types for database models."""

from enum import StrEnum


class ServiceStatus(StrEnum):
    """Status values for services."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class IncidentStatus(StrEnum):
    """Status values for incidents."""

    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


class IncidentImpact(StrEnum):
    """Impact levels for incidents."""

    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
