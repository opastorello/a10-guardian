import logging
import sys

from loguru import logger

from a10_guardian.core.config import settings


class InterceptHandler(logging.Handler):
    """
    Redirect standard logging to Loguru.
    """

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    """
    Configure Loguru logging.
    """
    # Remove default handlers
    logger.remove()

    # Determine level
    level = settings.LOG_LEVEL

    # Add console handler
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        colorize=True,
        backtrace=settings.DEBUG,
        diagnose=settings.DEBUG,
    )

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Audit Logger configuration
    # Filter function for audit logs
    def audit_filter(record):
        return record["extra"].get("audit") is True

    # Add audit log file sink
    logger.add(
        "logs/audit.log",
        filter=audit_filter,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {extra[requester]} | {message}",
        rotation="10 MB",
        retention="30 days",
    )

    # Silence noisy libraries if needed (e.g. uvicorn access logs duplicate)

    # for _log in ["uvicorn", "uvicorn.error", "fastapi"]:
    #     _logger = logging.getLogger(_log)
    #     _logger.handlers = [InterceptHandler()]
