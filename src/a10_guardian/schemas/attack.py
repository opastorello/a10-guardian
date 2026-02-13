"""Pydantic schemas for attack/incident monitoring endpoints.

These schemas define the structure for DDoS attack/incident monitoring responses,
including ongoing incidents, statistics, and detailed information.

Example Success Response (Ongoing Incidents):
    {
        "total": 2,
        "page": 1,
        "items_per_page": 20,
        "incidents": [
            {
                "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "zone_name": "203.0.113.50",
                "zone_id": "f6593c0b-9c93-4736-babc-8a3828e35af6",
                "severity": "High",
                "start_time": "2026-02-13T10:15:30Z",
                "status": "Ongoing"
            },
            {
                "incident_id": "b2c3d4e5-f6a7-8901-bcde-ef2345678901",
                "zone_name": "198.51.100.75",
                "zone_id": "a3b4c5d6-7890-1234-cdef-567890abcdef",
                "severity": "Medium",
                "start_time": "2026-02-13T10:20:15Z",
                "status": "Ongoing"
            }
        ]
    }

Example Success Response (Incident Stats):
    {
        "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "zone_name": "203.0.113.50",
        "total_packets": 15000000,
        "total_bytes": 7500000000,
        "peak_pps": 500000,
        "peak_bps": 4000000000,
        "attack_vectors": [
            {"protocol": "UDP", "port": 53, "percentage": 65},
            {"protocol": "TCP", "port": 80, "percentage": 25},
            {"protocol": "ICMP", "port": null, "percentage": 10}
        ],
        "error": null
    }

Example Error Response (Incident Not Found):
    {
        "error": "Incident not found or no stats available",
        "incident_id": "invalid-uuid-here"
    }
"""

from typing import Any

from pydantic import BaseModel, Field


class IncidentItem(BaseModel):
    """Individual incident/attack item in the ongoing list.

    Represents a single active DDoS attack with basic metadata.
    """

    incident_id: str = Field(
        ...,
        description="Unique identifier for the incident (UUID)",
        json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
    )
    zone_name: str = Field(
        ...,
        description="Protected IP address or zone name under attack",
        json_schema_extra={"example": "203.0.113.50"},
    )
    zone_id: str | None = Field(
        None,
        description="UUID of the protection zone in A10",
        json_schema_extra={"example": "f6593c0b-9c93-4736-babc-8a3828e35af6"},
    )
    severity: str | None = Field(
        None,
        description="Attack severity level (Low, Medium, High, Critical)",
        json_schema_extra={"example": "High"},
    )
    start_time: str | None = Field(
        None,
        description="ISO 8601 timestamp when attack started",
        json_schema_extra={"example": "2026-02-13T10:15:30Z"},
    )
    status: str | None = Field(
        None, description="Current status of the incident", json_schema_extra={"example": "Ongoing"}
    )


class OngoingIncidentsResponse(BaseModel):
    """Response for GET /api/v1/attacks/ongoing endpoint.

    Returns paginated list of all ongoing DDoS attacks across all protected zones.
    """

    total: int = Field(
        ..., description="Total number of ongoing incidents across all pages", json_schema_extra={"example": 2}
    )
    page: int = Field(..., description="Current page number (1-indexed)", json_schema_extra={"example": 1})
    items_per_page: int = Field(..., description="Maximum items per page", json_schema_extra={"example": 20})
    incidents: list[IncidentItem] = Field(
        default_factory=list,
        description="List of ongoing attack incidents on this page",
        json_schema_extra={
            "example": [
                {
                    "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "zone_name": "203.0.113.50",
                    "zone_id": "f6593c0b-9c93-4736-babc-8a3828e35af6",
                    "severity": "High",
                    "start_time": "2026-02-13T10:15:30Z",
                    "status": "Ongoing",
                }
            ]
        },
    )


class IncidentStatsResponse(BaseModel):
    """Response for GET /api/v1/attacks/incident/{id}/stats endpoint.

    Provides detailed traffic statistics and attack vector breakdown for a specific incident.

    Example Success:
        {
            "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "zone_name": "203.0.113.50",
            "total_packets": 15000000,
            "total_bytes": 7500000000,
            "peak_pps": 500000,
            "peak_bps": 4000000000,
            "attack_vectors": [{"protocol": "UDP", "port": 53, "percentage": 65}],
            "error": null
        }

    Example Failure:
        {
            "error": "Incident not found or no stats available",
            "incident_id": "invalid-id"
        }
    """

    incident_id: str | None = Field(
        None, description="UUID of the incident", json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    )
    zone_name: str | None = Field(
        None, description="Protected IP under attack", json_schema_extra={"example": "203.0.113.50"}
    )
    total_packets: int | None = Field(
        None, description="Total packet count during incident lifetime", json_schema_extra={"example": 15000000}
    )
    total_bytes: int | None = Field(
        None, description="Total bytes transferred during incident", json_schema_extra={"example": 7500000000}
    )
    peak_pps: int | None = Field(
        None, description="Peak packets per second observed", json_schema_extra={"example": 500000}
    )
    peak_bps: int | None = Field(
        None, description="Peak bits per second observed", json_schema_extra={"example": 4000000000}
    )
    attack_vectors: list[dict[str, Any]] | None = Field(
        None,
        description="Breakdown of attack by protocol/port",
        json_schema_extra={"example": [{"protocol": "UDP", "port": 53, "percentage": 65}]},
    )
    error: str | None = Field(None, description="Error message if stats unavailable (null on success)")


class IncidentDetailsResponse(BaseModel):
    """Response for GET /api/v1/attacks/incident/{id}/details endpoint.

    Returns complete incident data from A10, including all available fields and raw JSON.

    Example Success:
        {
            "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "zone_name": "203.0.113.50",
            "zone_id": "f6593c0b-9c93-4736-babc-8a3828e35af6",
            "severity": "High",
            "start_time": "2026-02-13T10:15:30Z",
            "end_time": null,
            "status": "Ongoing",
            "attack_type": "UDP Flood",
            "mitigation_applied": true,
            "raw_data": {"protocols_detected": ["UDP", "ICMP"], "target_ports": [53, 80]},
            "error": null
        }

    Example Failure:
        {
            "error": "Incident not found",
            "incident_id": "invalid-id"
        }
    """

    incident_id: str | None = Field(
        None, description="UUID of the incident", json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    )
    zone_name: str | None = Field(
        None, description="Protected IP under attack", json_schema_extra={"example": "203.0.113.50"}
    )
    zone_id: str | None = Field(
        None, description="A10 zone UUID", json_schema_extra={"example": "f6593c0b-9c93-4736-babc-8a3828e35af6"}
    )
    severity: str | None = Field(
        None, description="Attack severity (Low/Medium/High/Critical)", json_schema_extra={"example": "High"}
    )
    start_time: str | None = Field(
        None, description="ISO 8601 attack start timestamp", json_schema_extra={"example": "2026-02-13T10:15:30Z"}
    )
    end_time: str | None = Field(
        None, description="ISO 8601 attack end timestamp (null if ongoing)", json_schema_extra={"example": None}
    )
    status: str | None = Field(
        None, description="Incident status (Ongoing, Mitigated, Resolved)", json_schema_extra={"example": "Ongoing"}
    )
    attack_type: str | None = Field(
        None,
        description="Classified attack type (e.g., UDP Flood, SYN Flood)",
        json_schema_extra={"example": "UDP Flood"},
    )
    mitigation_applied: bool | None = Field(
        None, description="Whether automatic mitigation was triggered", json_schema_extra={"example": True}
    )
    raw_data: dict[str, Any] | None = Field(
        None,
        description="Full raw incident JSON from A10 API",
        json_schema_extra={"example": {"protocols_detected": ["UDP", "ICMP"], "target_ports": [53, 80]}},
    )
    error: str | None = Field(None, description="Error message if details unavailable (null on success)")
