from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.services.attack_service import AttackService
from a10_guardian.services.mitigation_service import MitigationService
from a10_guardian.services.notification_service import NotificationService
from a10_guardian.services.system_service import SystemService
from a10_guardian.services.template_service import TemplateService

# Define the API Key security scheme for Swagger UI integration
api_key_header = APIKeyHeader(name="x-api-token", auto_error=True)


async def verify_api_token(api_key: str = Security(api_key_header)):
    """
    Validates the API token from the header.
    Using Security() ensures it appears in the Swagger UI Authorize button.
    """
    if api_key != settings.API_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API Token")
    return api_key


def get_a10_client():
    return A10Client(settings.A10_USERNAME, settings.A10_PASSWORD)


def get_notification_service() -> NotificationService:
    return NotificationService()


def get_system_service(client: A10Client = Depends(get_a10_client)) -> SystemService:
    return SystemService(client)


def get_mitigation_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> MitigationService:
    return MitigationService(client, notifier)


def get_template_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> TemplateService:
    return TemplateService(client, notifier)


def get_attack_service(
    client: A10Client = Depends(get_a10_client), notifier: NotificationService = Depends(get_notification_service)
) -> AttackService:
    return AttackService(client, notifier)
