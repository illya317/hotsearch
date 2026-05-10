"""Logging utilities.

Usage:
    from hotsearch.tools.logger import get_logger
    logger = get_logger(__name__)
    logger.info("message")

Or initialize at app startup:
    from hotsearch.tools.logger import setup_logging
    setup_logging()
"""

import logging
import logging.config
from pathlib import Path

import yaml  # type: ignore[import]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LOG_CONFIG_PATH = _PROJECT_ROOT / "config" / "logging_config.yaml"

_initialized = False


def setup_logging() -> None:
    """Load logging config from config/logging_config.yaml."""
    global _initialized
    if _initialized:
        return
    if not _LOG_CONFIG_PATH.exists():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
        _initialized = True
        return
    cfg = yaml.safe_load(_LOG_CONFIG_PATH.read_text(encoding="utf-8"))
    if cfg and "logging" in cfg:
        logging.config.dictConfig(cfg["logging"])
    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance. Auto-initializes logging on first call."""
    if not _initialized:
        setup_logging()
    return logging.getLogger(name)
