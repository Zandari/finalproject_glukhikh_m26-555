"""Singleton-загрузчик настроек из [tool.valutatrade] в pyproject.toml."""

import tomllib
from pathlib import Path
from typing import Any


class SettingsLoader:
    """Единственный объект настроек; __new__ выбран за простоту реализации."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.project_root = Path(__file__).resolve().parents[2]
        self._settings: dict[str, Any] = {
            "DATA_DIR": "data",
            "USERS_FILE": "data/users.json",
            "PORTFOLIOS_FILE": "data/portfolios.json",
            "RATES_FILE": "data/rates.json",
            "HISTORY_FILE": "data/exchange_rates.json",
            "RATES_TTL_SECONDS": 300,
            "BASE_CURRENCY": "USD",
            "LOG_DIR": "logs",
            "LOG_LEVEL": "INFO",
        }
        self.reload()
        self.__class__._initialized = True

    def reload(self) -> None:
        """Перечитать секцию настроек из pyproject.toml."""
        config_path = self.project_root / "pyproject.toml"
        if config_path.exists():
            with config_path.open("rb") as file:
                config = tomllib.load(file)
            self._settings.update(config.get("tool", {}).get("valutatrade", {}))

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение настройки с необязательным значением по умолчанию."""
        return self._settings.get(key, default)

    def path(self, key: str) -> Path:
        """Преобразовать путь из настройки в абсолютный путь проекта."""
        value = Path(self.get(key))
        return value if value.is_absolute() else self.project_root / value
