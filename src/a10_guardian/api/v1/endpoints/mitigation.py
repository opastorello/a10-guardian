from fastapi import APIRouter, Depends, HTTPException

from a10_guardian.core.dependencies import get_mitigation_service, verify_api_token
from a10_guardian.schemas.common import GenericResponse
from a10_guardian.schemas.mitigation import ZoneListResponse, ZoneStatusResponse
from a10_guardian.services.mitigation_service import MitigationService

router = APIRouter(prefix="/mitigation", tags=["Mitigation"], dependencies=[Depends(verify_api_token)])

MITIGATE_DESC = (
    "All-in-one mitigation. Creates zone + monitor + deploy from the Golden Payload"
    " if missing, or re-deploys/syncs to TPS devices if the zone already exists."
)


@router.post("/zones/mitigate/{ip}", response_model=GenericResponse, summary="Mitigate IP", description=MITIGATE_DESC)
def ensure_mitigation(
    ip: str, template: str | None = None, service: MitigationService = Depends(get_mitigation_service)
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


@router.delete(
    "/zones/remove/{ip}",
    response_model=GenericResponse,
    summary="Remove Zone",
    description="Stop mitigation and delete the zone for a specific IP address.",
)
def remove_zone(ip: str, service: MitigationService = Depends(get_mitigation_service)):
    try:
        return service.remove_zone(ip)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
