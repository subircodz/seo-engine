"""Development entry point: ``python -m sie`` or the installed ``sie`` script."""

import uvicorn

from sie.config import get_settings
from sie.logging import setup_logging


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    uvicorn.run(
        "sie.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug and not settings.is_production,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
