"""
Lead Generation v2 — Logging
Live log to file + console with timestamps.
"""

import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = "data/logs"


def setup_logging(run_id: str = None) -> logging.Logger:
    """Configure root logger: console + file, both with timestamps."""
    os.makedirs(LOG_DIR, exist_ok=True)

    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    log_file = os.path.join(LOG_DIR, f"run_{run_id}.log")

    logger = logging.getLogger("leadgen")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    logger.info(f"Log file: {log_file}")
    return logger


def get_logger() -> logging.Logger:
    """Get the leadgen logger (or create default if not set up)."""
    logger = logging.getLogger("leadgen")
    if not logger.handlers:
        return setup_logging()
    return logger
