"""Координатор обновления курсов из нескольких API-источников."""

from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_logger


class RatesUpdater:
    """Последовательно опрашивает API-клиенты и сохраняет общий снимок."""

    def __init__(self, clients: list, storage) -> None:
        self.clients = clients
        self.storage = storage
        self.logger = get_logger("parser")

    def run_update(self, source: str | None = None) -> dict:
        """Обновить доступные источники; сбой одного не мешает остальным."""
        self.logger.info("Starting rates update")
        selected = [
            c
            for c in self.clients
            if source is None or c.source.lower().replace("-api", "") == source.lower()
        ]
        if source and not selected:
            raise ValueError(f"Неизвестный источник '{source}'")
        updates = {}
        errors = []
        for client in selected:
            try:
                self.logger.info("Fetching from %s", client.source)
                rates = client.fetch_rates()
                timestamp = (
                    datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                )
                for pair, value in rates.items():
                    if not isinstance(value, (int, float)) or value <= 0:
                        self.logger.warning("Skipping invalid rate %s=%r", pair, value)
                        continue
                    updates[pair] = {
                        "rate": float(value),
                        "source": client.source,
                        "updated_at": timestamp,
                    }
                self.logger.info("Fetched %s rates from %s", len(rates), client.source)
            except Exception as exc:  # ошибка одного источника не останавливает остальные
                errors.append(f"{client.source}: {exc}")
                self.logger.exception("Failed to fetch from %s", client.source)
        if updates:
            self.storage.save_update(updates)
            self.logger.info("Wrote %s rates to cache", len(updates))
        if not updates and errors:
            raise ApiRequestError("; ".join(errors))
        self.logger.info("Rates update finished: %s rates, %s errors", len(updates), len(errors))
        return {
            "updated": len(updates),
            "errors": errors,
            "last_refresh": datetime.now(timezone.utc).isoformat(),
        }
