"""Centralised, Rich-backed logging.

Application modules only ever call :func:`get_logger`. Handler installation
happens exactly once, at process bootstrap (:func:`setup_logging`).
"""

import logging

from rich.logging import RichHandler

_configured = False

_NOISY_LOGGERS = ("httpx", "httpcore", "sqlalchemy.engine")


def setup_logging(level: str = "INFO") -> None:
    """Install the root RichHandler once per process; later calls adjust level only."""
    global _configured
    resolved = getattr(logging, level.upper(), logging.INFO)

    if _configured:
        logging.getLogger().setLevel(resolved)
        return

    handler = RichHandler(rich_tracebacks=True, show_path=False, markup=True)
    handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    logging.basicConfig(level=resolved, handlers=[handler])

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
