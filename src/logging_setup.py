"""Life OS — настройка логирования.

Два назначения логов по правилам проекта:
1. Файл logs/lifeos.log (+ консоль) — модуль logging, ротация по размеру.
2. Таблица pipeline_log в SQLite — через src.db.log_failure (ошибки конвейера
   не прерывают процесс, а фиксируются со статусом failed).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    """Идемпотентная настройка корневого логгера lifeos."""
    global _CONFIGURED
    logger = logging.getLogger("lifeos")
    if _CONFIGURED:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "lifeos.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    _CONFIGURED = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Дочерний логгер: get_logger('pipeline') -> lifeos.pipeline."""
    return logging.getLogger(f"lifeos.{name}")
