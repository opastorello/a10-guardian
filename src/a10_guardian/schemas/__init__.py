"""Pydantic schemas for API request/response validation."""

from a10_guardian.schemas.attack import (
    IncidentDetailsResponse,
    IncidentItem,
    IncidentStatsResponse,
    OngoingIncidentsResponse,
)
from a10_guardian.schemas.common import GenericResponse
from a10_guardian.schemas.mitigation import ZoneListItem, ZoneListResponse, ZoneStatusResponse
from a10_guardian.schemas.system import DeviceInfo, LicenseInfo, SystemInfoResponse
from a10_guardian.schemas.template import (
    TemplateListItem,
    TemplateResponse,
    TemplateValidationResult,
    ZoneTemplate,
)

__all__ = [
    # Common
    "GenericResponse",
    # System
    "SystemInfoResponse",
    "DeviceInfo",
    "LicenseInfo",
    # Mitigation
    "ZoneStatusResponse",
    "ZoneListResponse",
    "ZoneListItem",
    # Templates
    "ZoneTemplate",
    "TemplateResponse",
    "TemplateListItem",
    "TemplateValidationResult",
    # Attacks
    "OngoingIncidentsResponse",
    "IncidentItem",
    "IncidentStatsResponse",
    "IncidentDetailsResponse",
]
