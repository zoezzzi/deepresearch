import sys
from loguru import logger
from .config import get_harness_settings

settings = get_harness_settings()

logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True
)

logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    backtrace=True,
    diagnose=True
)

__all__ = ["logger"]
