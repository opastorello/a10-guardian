import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from a10_guardian.api.v1.api import api_router
from a10_guardian.core.client import A10Client
from a10_guardian.core.config import settings
from a10_guardian.core.dependencies import get_a10_client
from a10_guardian.core.exceptions import (
    TemplateA10ValidationError,
    TemplateNotFoundError,
    TemplateValidationError,
    generic_exception_handler,
    http_exception_handler,
    template_a10_validation_handler,
    template_not_found_handler,
    template_validation_handler,
    validation_exception_handler,
)
from a10_guardian.core.limiter import limiter
from a10_guardian.core.logging import setup_logging
from a10_guardian.services.attack_service import AttackService
from a10_guardian.services.notification_service import NotificationService


async def monitor_a10_health():
    """Background task to monitor A10 device health and send notifications on status changes."""
    notifier = NotificationService()
    client = A10Client(username=settings.A10_USERNAME, password=settings.A10_PASSWORD)
    last_status = None
    check_interval = 60  # Check every 60 seconds

    while True:
        try:
            await asyncio.sleep(check_interval)

            # Try to connect to A10
            try:
                client.connect()
                current_status = "online"
            except Exception:
                current_status = "offline"

            # Send notification only when status changes
            if last_status is not None and current_status != last_status:
                if current_status == "offline":
                    notifier.send_notification(
                        title="A10 Device Offline",
                        message="A10 Thunder TPS device is not responding",
                        level="error",
                        fields={
                            "Device": settings.A10_BASE_URL,
                            "Status": "Offline",
                            "Previous": "Online",
                        },
                        event_type="a10_offline",
                    )
                    logger.error(f"A10 health check FAILED - device offline: {settings.A10_BASE_URL}")
                else:
                    notifier.send_notification(
                        title="A10 Device Recovered",
                        message="A10 Thunder TPS device connection restored",
                        level="success",
                        fields={
                            "Device": settings.A10_BASE_URL,
                            "Status": "Online",
                            "Previous": "Offline",
                        },
                        event_type="a10_recovered",
                    )
                    logger.info(f"A10 health check RECOVERED - device back online: {settings.A10_BASE_URL}")

            last_status = current_status

        except asyncio.CancelledError:
            logger.info("A10 health monitoring stopped")
            break
        except Exception as e:
            logger.error(f"Error in A10 health monitor: {e}")


async def monitor_ddos_attacks():
    """Background task to monitor DDoS attacks and send real-time notifications."""
    notifier = NotificationService()
    client = A10Client(username=settings.A10_USERNAME, password=settings.A10_PASSWORD)
    attack_service = AttackService(client, notifier)

    # Track incidents we've already notified about
    known_incidents = {}  # {incident_id: {"start_time": timestamp, "notified_at": timestamp}}

    check_interval = max(10, min(settings.ATTACK_MONITORING_INTERVAL, 300))  # Clamp between 10-300s
    logger.info(f"Attack monitoring interval: {check_interval}s")

    while True:
        try:
            await asyncio.sleep(check_interval)

            # Fetch ongoing incidents
            try:
                result = attack_service.get_ongoing_incidents(page=1, items=100)
                current_incidents = result.get("incidents", [])
            except Exception as e:
                logger.error(f"Failed to fetch incidents: {e}")
                continue

            current_incident_ids = set()

            # Process each incident
            for incident in current_incidents:
                incident_id = incident.get("incident_id")
                if not incident_id:
                    continue

                current_incident_ids.add(incident_id)

                # New attack detected
                if incident_id not in known_incidents:
                    logger.warning(f"NEW ATTACK DETECTED: {incident.get('zone_name')} - {incident_id}")
                    attack_service.notify_attack_detected(incident)
                    known_incidents[incident_id] = {
                        "start_time": incident.get("start_time"),
                        "first_seen": asyncio.get_event_loop().time(),
                    }

                # Check for ongoing attack notifications (every 15min)
                elif settings.NOTIFY_ATTACK_ONGOING:
                    elapsed = asyncio.get_event_loop().time() - known_incidents[incident_id]["first_seen"]
                    attack_service.notify_attack_ongoing(incident, int(elapsed))

            # Detect mitigated/ended attacks (incidents that disappeared from ongoing list)
            mitigated_ids = set(known_incidents.keys()) - current_incident_ids
            for incident_id in mitigated_ids:
                incident_data = known_incidents[incident_id]
                elapsed = asyncio.get_event_loop().time() - incident_data["first_seen"]

                logger.info(f"ATTACK MITIGATED: {incident_id} (duration: {int(elapsed)}s)")
                # Create a minimal incident dict for notification
                attack_service.notify_attack_mitigated(
                    {"incident_id": incident_id, "zone_name": "Unknown", "severity": "Unknown"},
                    int(elapsed),
                )
                del known_incidents[incident_id]

        except asyncio.CancelledError:
            logger.info("Attack monitoring stopped")
            break
        except Exception as e:
            logger.error(f"Error in attack monitor: {e}")


async def monitor_zone_changes():
    """Background task to monitor zone configuration changes."""
    from a10_guardian.services.zone_change_service import ZoneChangeService

    notifier = NotificationService()
    client = A10Client(username=settings.A10_USERNAME, password=settings.A10_PASSWORD)
    zone_service = ZoneChangeService(client, notifier)

    check_interval = max(10, min(settings.ZONE_MONITORING_INTERVAL, 300))  # Clamp between 10-300s
    logger.info(f"Zone change monitoring interval: {check_interval}s")

    # Initial populate - load existing zones without notifying
    try:
        logger.info("Performing initial zone population (no notifications)...")
        initial_zones = zone_service.fetch_all_zones()
        for zone_id, zone_data in initial_zones.items():
            zone_service.known_zones[zone_id] = {
                "snapshot": zone_data,
                "first_seen": asyncio.get_event_loop().time(),
            }
        logger.info(f"Initial population complete: {len(initial_zones)} zones loaded")
    except Exception as e:
        logger.error(f"Failed initial zone population: {e}")

    while True:
        try:
            await asyncio.sleep(check_interval)

            # Fetch current zones
            try:
                current_zones = zone_service.fetch_all_zones()
            except Exception as e:
                logger.error(f"Failed to fetch zones: {e}")
                continue

            # Detect changes
            new_ids, deleted_ids, modified_ids = zone_service.detect_zone_changes(current_zones)

            # Process new zones
            for zone_id in new_ids:
                zone_service.notify_zone_created(current_zones[zone_id])
                zone_service.known_zones[zone_id] = {
                    "snapshot": current_zones[zone_id],
                    "first_seen": asyncio.get_event_loop().time(),
                }

            # Process modified zones
            for zone_id in modified_ids:
                old = zone_service.known_zones[zone_id]["snapshot"]
                new = current_zones[zone_id]
                zone_service.notify_zone_modified(zone_id, old, new)
                zone_service.known_zones[zone_id]["snapshot"] = new

            # Process deleted zones
            for zone_id in deleted_ids:
                zone_service.notify_zone_deleted(zone_id, zone_service.known_zones[zone_id]["snapshot"])
                del zone_service.known_zones[zone_id]

        except asyncio.CancelledError:
            logger.info("Zone change monitoring stopped")
            break
        except Exception as e:
            logger.error(f"Error in zone monitor: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging on startup
    setup_logging()
    logger.info("Starting A10 Guardian API")

    # Initialize template directory
    from pathlib import Path

    template_dir = Path(settings.TEMPLATE_DIR)
    template_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Template directory ready: {template_dir.absolute()}")

    # Check if templates exist
    templates = list(template_dir.glob("*.json"))
    if not templates:
        logger.warning(
            "⚠️  NO TEMPLATES CONFIGURED! You must create at least one template "
            "before using mitigation endpoints. Use POST /api/v1/templates/<name>"
        )
    else:
        logger.info(f"Found {len(templates)} template(s): {[t.stem for t in templates]}")

    # Start A10 health monitoring if enabled
    health_monitor_task = None
    if settings.NOTIFY_SYSTEM_HEALTH:
        logger.info("Starting A10 health monitoring (60s interval)")
        health_monitor_task = asyncio.create_task(monitor_a10_health())

    # Start attack monitoring if enabled
    attack_monitor_task = None
    if settings.NOTIFY_ATTACK_DETECTED or settings.NOTIFY_ATTACK_MITIGATED:
        logger.info(f"Starting DDoS attack monitoring ({settings.ATTACK_MONITORING_INTERVAL}s interval)")
        attack_monitor_task = asyncio.create_task(monitor_ddos_attacks())

    # Start zone change monitoring if enabled
    zone_monitor_task = None
    if settings.NOTIFY_ZONE_CREATED or settings.NOTIFY_ZONE_MODIFIED or settings.NOTIFY_ZONE_DELETED:
        logger.info(f"Starting zone change monitoring ({settings.ZONE_MONITORING_INTERVAL}s interval)")
        zone_monitor_task = asyncio.create_task(monitor_zone_changes())

    yield

    # Stop monitoring tasks
    logger.info("Shutting down A10 Guardian API")
    if health_monitor_task:
        health_monitor_task.cancel()
        try:
            await asyncio.wait_for(health_monitor_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    if attack_monitor_task:
        attack_monitor_task.cancel()
        try:
            await asyncio.wait_for(attack_monitor_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    if zone_monitor_task:
        zone_monitor_task.cancel()
        try:
            await asyncio.wait_for(zone_monitor_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass


APP_DESCRIPTION = (
    "REST API wrapper for A10 Networks Thunder TPS DDoS mitigation devices."
    " Manages protected zones, monitors active incidents, and provides system health metrics."
)

app = FastAPI(
    title="A10 Guardian API",
    version="1.0.0",
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Global Error Handling
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(TemplateNotFoundError, template_not_found_handler)
app.add_exception_handler(TemplateValidationError, template_validation_handler)
app.add_exception_handler(TemplateA10ValidationError, template_a10_validation_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def read_root():
    return {"message": "Welcome to the A10 Guardian API Wrapper"}


@app.get("/health", tags=["System"])
def health_check(check_upstream: bool = False, client: A10Client = Depends(get_a10_client)):
    status = {"status": "ok", "app": "up"}
    if check_upstream:
        try:
            client.connect()
            status["upstream"] = "connected"
        except Exception as e:
            status["upstream"] = "down"
            status["error"] = str(e)
            raise HTTPException(status_code=503, detail=status) from e
    return status
