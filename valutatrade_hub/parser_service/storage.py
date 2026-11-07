"""Хранилище последнего снимка rates.json и истории exchange_rates.json."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class RatesStorage:
    """Атомарная запись актуальных курсов и истории измерений."""

    def __init__(self, rates_path: str | Path, history_path: str | Path) -> None:
        self.rates_path = Path(rates_path)
        self.history_path = Path(history_path)

    @staticmethod
    def _read(path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    @staticmethod
    def _atomic_write(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def save_update(self, updates: dict[str, dict]) -> None:
        """Обновить кеш и добавить уникальные записи в историю."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        cache = self._read(self.rates_path, {"pairs": {}, "last_refresh": None})
        cache.setdefault("pairs", {})
        history = self._read(self.history_path, [])
        if isinstance(history, dict):
            history = history.get("records", [])
        known_ids = {item.get("id") for item in history if isinstance(item, dict)}
        for pair, info in updates.items():
            from_code, to_code = pair.split("_", maxsplit=1)
            timestamp = info.get("updated_at", now)
            rate = float(info["rate"])
            previous = cache["pairs"].get(pair)
            if previous and previous.get("updated_at", "") > timestamp:
                continue
            cache["pairs"][pair] = {
                "rate": rate,
                "updated_at": timestamp,
                "source": info.get("source", "unknown"),
            }
            record_id = f"{from_code}_{to_code}_{timestamp}"
            if record_id not in known_ids:
                history.append(
                    {
                        "id": record_id,
                        "from_currency": from_code,
                        "to_currency": to_code,
                        "rate": rate,
                        "timestamp": timestamp,
                        "source": info.get("source", "unknown"),
                        "meta": info.get("meta", {}),
                    }
                )
                known_ids.add(record_id)
        cache["last_refresh"] = now
        self._atomic_write(self.rates_path, cache)
        self._atomic_write(self.history_path, history)
