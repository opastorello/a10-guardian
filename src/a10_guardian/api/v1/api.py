from fastapi import APIRouter

from a10_guardian.api.v1.endpoints import attacks, mitigation, system, templates

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(mitigation.router)
api_router.include_router(templates.router)
api_router.include_router(attacks.router)
