"""Application logging setup.

Always logs to stdout (captured by podman/docker logs). When
HISABPRO_LOG_DIR is set, also writes to a rotating file
(hisabpro.log, 5 MB x 5 backups) so logs survive container restarts.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import LOG_DIR, LOG_LEVEL

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"

_configured = False


def configure_logging() -> None:
    """Idempotent: safe to call from app import and from tests."""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if LOG_DIR:
        log_path = Path(LOG_DIR)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path / "hisabpro.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # We emit one structured line per request from our own middleware;
    # silence uvicorn's duplicate access log.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
