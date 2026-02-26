# backend/core/logging.py
import logging
import sys
from config import settings

def setup_logging():
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Terminal handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler — saves logs to lifeos.log
    file_handler = logging.FileHandler("lifeos.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Root logger setup
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )

    # Silence noisy libraries
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger("lifeos")