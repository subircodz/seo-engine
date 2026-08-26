"""Centralised, Rich-backed logging.

Application modules only ever call :func:`get_logger`. Handler installation
happens exactly once, at process bootstrap (:func:`setup_logging`).
"""

import logging
from contextvars import ContextVar

from rich.logging import RichHandler

_configured = False

_NOISY_LOGGERS = ("httpx", "httpcore", "sqlalchemy.engine")

# Context variable to store request ID for the current async task
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Logging filter that injects request ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id:
            record.request_id = request_id
        else:
            record.request_id = "-"
        return True


def setup_logging(level: str = "INFO") -> None:
    """Install the root RichHandler once per process; later calls adjust level only."""
    global _configured
    resolved = getattr(logging, level.upper(), logging.INFO)

    if _configured:
        logging.getLogger().setLevel(resolved)
        return

    handler = RichHandler(rich_tracebacks=True, show_path=False, markup=True)
    # Include request_id in log format
    handler.setFormatter(
        logging.Formatter("%(message)s [request_id=%(request_id)s]", datefmt="[%X]")
    )
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(level=resolved, handlers=[handler])

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(request_id: str | None) -> None:
    """Set the request ID for the current context."""
    request_id_var.set(request_id)


def get_request_id() -> str | None:
    """Get the request ID for the current context."""
    return request_id_var.get()
