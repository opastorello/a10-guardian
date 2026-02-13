from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from a10_guardian.core.dependencies import get_system_service, verify_api_token
from a10_guardian.schemas.system import DeviceListResponse, LicenseInfo, SystemInfoResponse
from a10_guardian.services.system_service import SystemService

router = APIRouter(prefix="/system", tags=["System"], dependencies=[Depends(verify_api_token)])


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    summary="System Info",
    description="Retrieve hostname, version, serial number, and uptime from the A10 device.",
)
def get_system_info(service: SystemService = Depends(get_system_service)):
    try:
        return service.get_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/devices",
    response_model=DeviceListResponse | list[Any],
    summary="Device List",
    description="List all devices in the A10 inventory with model, firmware, serial, and IP.",
)
def get_device_list(service: SystemService = Depends(get_system_service)):
    try:
        return service.get_devices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/license",
    response_model=LicenseInfo,
    summary="License Info",
    description="License type, maximum devices/objects, and expiration date.",
)
def get_license_status(service: SystemService = Depends(get_system_service)):
    try:
        return service.get_license()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
