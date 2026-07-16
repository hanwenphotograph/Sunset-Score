from __future__ import annotations

import logging
from typing import TextIO


LOGGER_NAME = "sunsetscore"
logger = logging.getLogger(LOGGER_NAME)
logger.addHandler(logging.NullHandler())


class ChineseLevelFormatter(logging.Formatter):
    _level_names = {
        logging.DEBUG: "调试",
        logging.INFO: "信息",
        logging.WARNING: "警告",
        logging.ERROR: "错误",
        logging.CRITICAL: "严重错误",
    }

    def format(self, record: logging.LogRecord) -> str:
        original = record.levelname
        record.levelname = self._level_names.get(record.levelno, original)
        try:
            return super().format(record)
        finally:
            record.levelname = original


def configure_logging(stream: TextIO | None = None) -> None:
    """Configure deterministic CLI logging without touching the root logger."""

    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        ChineseLevelFormatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
