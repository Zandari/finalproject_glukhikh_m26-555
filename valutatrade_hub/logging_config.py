"""Единая настройка логов приложения с ротацией файлов."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging(level: str = "INFO", log_dir: str | Path = "logs") -> None:
    """Настроить actions.log и parser.log; повторно обработчики не добавляются."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(levelname)s %(asctime)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    for logger_name, filename in (("actions", "actions.log"), ("parser", "parser.log")):
        logger = logging.getLogger(logger_name)
        logger.setLevel(numeric_level)
        logger.propagate = False
        handler = RotatingFileHandler(
            directory / filename, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Вернуть настроенный логгер приложения."""
    setup_logging()
    return logging.getLogger(name)
