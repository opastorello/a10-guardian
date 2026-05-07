from fastapi import APIRouter, Depends, HTTPException, Request

from a10_guardian.core.dependencies import get_mitigation_service, require_scope
from a10_guardian.core.limiter import limiter
from a10_guardian.schemas.common import GenericResponse
from a10_guardian.schemas.mitigation import (
    UnderAttackResponse,
    ZoneIPCheckResponse,
    ZoneIPMutationResponse,
    ZoneListResponse,
    ZoneStatusResponse,
)
from a10_guardian.services.mitigation_service import MitigationService

router = APIRouter(prefix="/mitigation", tags=["Mitigation"])

MITIGATE_DESC = (
    "All-in-one mitigation. Creates zone + monitor + deploy from the Golden Payload"
    " if missing, or re-deploys/syncs to TPS devices if the zone already exists."
)


@router.post(
    "/zones/mitigate/{ip}",
    response_model=GenericResponse,
    summary="Mitigate IP",
    description=MITIGATE_DESC,
    dependencies=[Depends(require_scope("mitigation:write"))],
)
@limiter.limit("20/minute")
def ensure_mitigation(
    request: Request,
    ip: str,
    template: str | None = None,
    service: MitigationService = Depends(get_mitigation_service),
):
    """Mitigate an IP address using a specific template.

    Args:
        ip: IP address to mitigate
        template: Template name to use. If not specified, auto-selects if only one template exists.
    """
    try:
        result = service.ensure_mitigation(ip, template=template)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return GenericResponse(message=result.get("message"), status=result.get("status"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/zones/list",
    response_model=ZoneListResponse,
    summary="List Zones",
    description="Paginated list of all protected zones.",
    dependencies=[Depends(require_scope("mitigation:read"))],
)
def list_zones(service: MitigationService = Depends(get_mitigation_service), page: int = 1, items: int = 40):
    try:
        return service.list_zones(page, items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/zones/status/{ip}",
    response_model=ZoneStatusResponse,
    summary="Zone Status",
    description="Configuration and status of a specific zone by IP address.",
    dependencies=[Depends(require_scope("mitigation:read"))],
)
def get_zone_status(ip: str, service: MitigationService = Depends(get_mitigation_service)):
    try:
        result = service.get_zone_status(ip)
        if not result:
            raise HTTPException(status_code=404, detail=f"Zone not found for IP: {ip}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/under-attack/{ip}",
    response_model=UnderAttackResponse,
    summary="Under Attack Check",
    description="Returns whether the /24 block of a given IP is currently under attack (operational_mode=mitigation).",
    dependencies=[Depends(require_scope("mitigation:read"))],
)
def under_attack(ip: str, service: MitigationService = Depends(get_mitigation_service)):
    try:
        return service.is_under_attack(ip)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/zones/remove/{ip}",
    response_model=GenericResponse,
    summary="Remove Zone",
    description="Stop mitigation and delete the zone for a specific IP address.",
    dependencies=[Depends(require_scope("mitigation:write"))],
)
@limiter.limit("20/minute")
def remove_zone(
    request: Request,
    ip: str,
    service: MitigationService = Depends(get_mitigation_service),
):
    try:
        return service.remove_zone(ip)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/zones/{zone_name}/ip/{ip}",
    response_model=ZoneIPCheckResponse,
    summary="Check IP in Zone",
    description="Returns whether a specific IP is present in the zone's ip_list.",
    dependencies=[Depends(require_scope("mitigation:read"))],
)
def check_ip_in_zone(
    zone_name: str,
    ip: str,
    service: MitigationService = Depends(get_mitigation_service),
):
    try:
        return ZoneIPCheckResponse(found=service.has_ip_in_zone(zone_name, ip))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/zones/{zone_name}/ip/{ip}",
    response_model=ZoneIPMutationResponse,
    summary="Add IP to Zone",
    description="Adds an IP to the zone's ip_list. Idempotent: returns changed=false if already present.",
    dependencies=[Depends(require_scope("mitigation:write"))],
)
@limiter.limit("20/minute")
def add_ip_to_zone(
    request: Request,
    zone_name: str,
    ip: str,
    service: MitigationService = Depends(get_mitigation_service),
):
    try:
        return service.add_ip_to_zone(zone_name, ip)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/zones/{zone_name}/ip/{ip}",
    response_model=ZoneIPMutationResponse,
    summary="Remove IP from Zone",
    description="Removes an IP from the zone's ip_list. 404 if IP not present, 422 if it would empty the zone.",
    dependencies=[Depends(require_scope("mitigation:write"))],
)
@limiter.limit("20/minute")
def remove_ip_from_zone(
    request: Request,
    zone_name: str,
    ip: str,
    service: MitigationService = Depends(get_mitigation_service),
):
    try:
        return service.remove_ip_from_zone(zone_name, ip)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
