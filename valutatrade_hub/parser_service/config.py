"""Конфигурация API Parser Service."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParserConfig:
    """Параметры источников курсов и файлового хранилища."""

    EXCHANGERATE_API_KEY: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY")
    )
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    )
    RATES_FILE_PATH: Path = field(default_factory=lambda: Path("data/rates.json"))
    HISTORY_FILE_PATH: Path = field(default_factory=lambda: Path("data/exchange_rates.json"))
    REQUEST_TIMEOUT: int = 10

    def __post_init__(self) -> None:
        root = Path(__file__).resolve().parents[2]
        if not self.RATES_FILE_PATH.is_absolute():
            self.RATES_FILE_PATH = root / self.RATES_FILE_PATH
        if not self.HISTORY_FILE_PATH.is_absolute():
            self.HISTORY_FILE_PATH = root / self.HISTORY_FILE_PATH
