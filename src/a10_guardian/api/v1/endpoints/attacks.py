"""REST API endpoints for attack/incident monitoring."""

from fastapi import APIRouter, Depends, Query

from a10_guardian.core.dependencies import get_attack_service
from a10_guardian.schemas.attack import (
    IncidentDetailsResponse,
    IncidentStatsResponse,
    OngoingIncidentsResponse,
)
from a10_guardian.services.attack_service import AttackService

router = APIRouter(prefix="/attacks", tags=["Attack Monitoring"])


@router.get("/ongoing", response_model=OngoingIncidentsResponse, summary="List ongoing DDoS attacks")
def list_ongoing_attacks(
    page: int = Query(default=1, ge=1, description="Page number"),
    items: int = Query(default=20, ge=1, le=100, description="Items per page"),
    attack_service: AttackService = Depends(get_attack_service),
):
    """Fetch list of ongoing DDoS attacks/incidents from A10 Thunder TPS.

    Returns real-time data about active DDoS incidents, including zone information,
    severity levels, and timestamps. Updates every 10 seconds (configurable).

    Returns:
        OngoingIncidentsResponse: Paginated list of ongoing attacks with metadata
    """
    return attack_service.get_ongoing_incidents(page=page, items=items)


@router.get(
    "/incident/{incident_id}/stats",
    response_model=IncidentStatsResponse,
    summary="Get attack statistics",
    responses={
        200: {
            "description": "Incident statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "zone_name": "203.0.113.50",
                        "total_packets": 15000000,
                        "total_bytes": 7500000000,
                        "peak_pps": 500000,
                        "peak_bps": 4000000000,
                        "attack_vectors": [{"protocol": "UDP", "port": 53, "percentage": 65}],
                        "error": None,
                    }
                }
            },
        },
        404: {
            "description": "Incident not found",
            "content": {"application/json": {"example": {"error": "Incident not found", "incident_id": "invalid-id"}}},
        },
    },
)
def get_attack_stats(
    incident_id: str,
    attack_service: AttackService = Depends(get_attack_service),
):
    """Get detailed traffic statistics for a specific DDoS attack/incident.

    Provides metrics including packet/byte counts, peak rates, and attack vector breakdown.

    Args:
        incident_id: UUID of the incident to retrieve stats for

    Returns:
        IncidentStatsResponse: Detailed traffic and attack vector statistics
    """
    stats = attack_service.get_incident_stats(incident_id)
    if not stats:
        return {"error": "Incident not found or no stats available", "incident_id": incident_id}
    return stats


@router.get(
    "/incident/{incident_id}/details",
    response_model=IncidentDetailsResponse,
    summary="Get full incident details",
    responses={
        200: {
            "description": "Full incident details retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "zone_name": "203.0.113.50",
                        "zone_id": "f6593c0b-9c93-4736-babc-8a3828e35af6",
                        "severity": "High",
                        "start_time": "2026-02-13T10:15:30Z",
                        "end_time": None,
                        "status": "Ongoing",
                        "attack_type": "UDP Flood",
                        "mitigation_applied": True,
                        "raw_data": {"protocols_detected": ["UDP", "ICMP"], "target_ports": [53, 80]},
                        "error": None,
                    }
                }
            },
        },
        404: {
            "description": "Incident not found",
            "content": {"application/json": {"example": {"error": "Incident not found", "incident_id": "invalid-id"}}},
        },
    },
)
def get_attack_details(
    incident_id: str,
    attack_service: AttackService = Depends(get_attack_service),
):
    """Get complete JSON details for a specific DDoS attack/incident from A10.

    Includes all available fields such as severity, timestamps, attack classification,
    and raw incident data from the TPS device.

    Args:
        incident_id: UUID of the incident to retrieve

    Returns:
        IncidentDetailsResponse: Complete incident information including raw A10 data
    """
    details = attack_service.get_incident_details(incident_id)
    if not details:
        return {"error": "Incident not found", "incident_id": incident_id}
    return details
