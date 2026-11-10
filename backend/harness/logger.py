import sys

from loguru import logger

from .config import get_harness_settings
from .observability.log_formatter import get_trace_format, trace_context_filter

settings = get_harness_settings()

logger.remove()
logger.add(
    sys.stdout,
    format=get_trace_format(),
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
    filter=trace_context_filter,
)

logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    format=get_trace_format(),
    level="INFO",
    backtrace=True,
    diagnose=True,
    filter=trace_context_filter,
)

__all__ = ["logger"]
