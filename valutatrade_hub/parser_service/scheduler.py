"""Простой планировщик периодического обновления без сторонней библиотеки."""

import logging
import time


def run_periodically(updater, interval_seconds: int = 300) -> None:
    """Запускать обновление через заданный интервал до остановки процесса."""
    if interval_seconds < 1:
        raise ValueError("interval_seconds должен быть положительным")
    logger = logging.getLogger("parser")
    try:
        while True:
            try:
                updater.run_update()
            except Exception:
                logger.exception("Scheduled rates update failed")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Rates scheduler stopped by user")
