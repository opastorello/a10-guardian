"""API endpoints for zone template management."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Path as APIPath
from fastapi.responses import FileResponse

from a10_guardian.core.dependencies import get_template_service, require_scope
from a10_guardian.core.limiter import limiter
from a10_guardian.schemas.common import GenericResponse
from a10_guardian.schemas.template import (
    TemplateListItem,
    TemplateResponse,
    TemplateValidationResult,
    ZoneTemplate,
)
from a10_guardian.services.template_service import TemplateService

_NAME_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get(
    "/list",
    response_model=list[TemplateListItem],
    summary="List All Templates",
    description="Returns a list of all available zone templates in the template directory",
    dependencies=[Depends(require_scope("templates:read"))],
)
@limiter.limit("60/minute")
def list_templates(request: Request, service: TemplateService = Depends(get_template_service)):
    """List all template files with metadata."""
    try:
        return service.list_templates()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/{name}",
    response_model=TemplateResponse,
    summary="Get Template",
    description="Retrieves a specific template by name. Returns the full template with zone and monitor payloads.",
    dependencies=[Depends(require_scope("templates:read"))],
)
def get_template(
    name: str = APIPath(..., pattern=_NAME_PATTERN),
    service: TemplateService = Depends(get_template_service),
):
    """Get a specific template by name."""
    template_data = service.get_template(name)

    # Add metadata
    template_path = Path(service.template_dir) / f"{name}.json"
    stat = template_path.stat()

    return TemplateResponse(
        name=name,
        template=ZoneTemplate(**template_data),
        created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        file_size_kb=round(stat.st_size / 1024, 2),
    )


@router.post(
    "/{name}",
    response_model=GenericResponse,
    summary="Create/Update Template",
    description=(
        "Creates or updates a zone template. Performs structural validation (Pydantic) "
        "and A10 validation (checks if profiles/policies exist). Sends notification based on settings."
    ),
    dependencies=[Depends(require_scope("templates:write"))],
)
@limiter.limit("30/minute")
def create_or_update_template(
    request: Request,
    name: str = APIPath(..., pattern=_NAME_PATTERN),
    template: ZoneTemplate = ...,
    service: TemplateService = Depends(get_template_service),
):
    """Create or update a template with validation."""
    # Check if template exists to determine if it's an update
    template_path = Path(service.template_dir) / f"{name}.json"
    is_update = template_path.exists()

    # Ensure name matches
    template.name = name

    result = service.save_template(template.model_dump(), name, is_update=is_update)

    return GenericResponse(status=result["status"], message=result["message"])


@router.post(
    "/validate",
    response_model=TemplateValidationResult,
    summary="Validate Template (Dry-Run)",
    description=(
        "Validates a template without saving it. Performs both structural validation (Pydantic) "
        "and A10 validation (checks if profiles/policies exist in A10). Use this for pre-flight checks."
    ),
    dependencies=[Depends(require_scope("templates:read"))],
)
@limiter.limit("30/minute")
def validate_template(
    request: Request,
    template: ZoneTemplate,
    service: TemplateService = Depends(get_template_service),
):
    """Validate template without saving (dry-run)."""
    try:
        # Run A10 validation
        a10_result = service.validate_template_a10(template.model_dump())

        return TemplateValidationResult(valid=True, errors=[], a10_validation=a10_result)

    except Exception as e:
        return TemplateValidationResult(valid=False, errors=[str(e)], a10_validation={})


@router.delete(
    "/{name}",
    response_model=GenericResponse,
    summary="Delete Template",
    description="Deletes a template by name. The 'default' template is protected and cannot be deleted.",
    dependencies=[Depends(require_scope("templates:write"))],
)
@limiter.limit("20/minute")
def delete_template(
    request: Request,
    name: str = APIPath(..., pattern=_NAME_PATTERN),
    service: TemplateService = Depends(get_template_service),
):
    """Delete a template (except 'default' which is protected)."""
    service.delete_template(name)

    return GenericResponse(status="success", message=f"Template '{name}' deleted successfully")


@router.get(
    "/export/{name}",
    response_class=FileResponse,
    summary="Export Template",
    description="Downloads a template as a JSON file. Useful for backup or sharing templates.",
    dependencies=[Depends(require_scope("templates:read"))],
)
def export_template(
    name: str = APIPath(..., pattern=_NAME_PATTERN),
    service: TemplateService = Depends(get_template_service),
):
    """Export template as downloadable JSON file."""
    # Verify template exists (also validates name internally)
    service.get_template(name)

    template_path = Path(service.template_dir) / f"{name}.json"

    return FileResponse(
        path=str(template_path),
        media_type="application/json",
        filename=f"{name}-template.json",
        headers={"Content-Disposition": f'attachment; filename="{name}-template.json"'},
    )


@router.post(
    "/import/{ip}",
    response_model=GenericResponse,
    summary="Import Template from A10 Zone",
    description=(
        "Imports a template from an existing A10 zone. Fetches zone configuration by IP, "
        "extracts zone and monitor payloads, removes IP-specific fields, validates, and saves as a template."
    ),
    dependencies=[Depends(require_scope("templates:write"))],
)
@limiter.limit("10/minute")
def import_template_from_zone(
    request: Request,
    ip: str,
    name: str = Query(..., description="Name for the new template"),
    service: TemplateService = Depends(get_template_service),
):
    """Import template from existing A10 zone."""
    result = service.import_from_zone(ip, name)

    default_msg = f"Template '{name}' imported from zone {ip}"
    return GenericResponse(status="success", message=result.get("message", default_msg))
