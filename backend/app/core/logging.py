from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger

LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"


def setup_logging(level: str = "INFO") -> None:
    """Configure standard logging + Loguru."""

    logging.getLogger().handlers = []
    logger.remove()
    logger.add(sys.stdout, level=level.upper(), format=LOG_FORMAT, backtrace=True, diagnose=True)


class InterceptHandler(logging.Handler):
    """Bridge standard logging handlers to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def get_logger(name: str) -> Any:
    return logger.bind(module=name)
