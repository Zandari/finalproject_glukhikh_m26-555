"""Singleton JSON-хранилище с атомарной записью и блокировкой операций."""

import json
import os
from threading import RLock
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Единый менеджер users/portfolios/rates JSON-файлов."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.settings = SettingsLoader()
        self._lock = RLock()
        self.__class__._initialized = True

    def _read(self, key: str, default: Any) -> Any:
        path = self.settings.path(key)
        with self._lock:
            if not path.exists():
                return default
            try:
                with path.open("r", encoding="utf-8") as file:
                    return json.load(file)
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(f"Не удалось прочитать {path}: {exc}") from exc

    def _write(self, key: str, data: Any) -> None:
        path = self.settings.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with self._lock:
            try:
                with temp_path.open("w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temp_path, path)
            finally:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)

    def load_users(self) -> list[dict]:
        return self._read("USERS_FILE", [])

    def save_users(self, data: list[dict]) -> None:
        self._write("USERS_FILE", data)

    def load_portfolios(self) -> list[dict]:
        return self._read("PORTFOLIOS_FILE", [])

    def save_portfolios(self, data: list[dict]) -> None:
        self._write("PORTFOLIOS_FILE", data)

    def load_rates(self) -> dict:
        return self._read("RATES_FILE", {"pairs": {}, "last_refresh": None})

    def save_rates(self, data: dict) -> None:
        self._write("RATES_FILE", data)
