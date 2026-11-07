"""Иерархия валют и фабрика для получения объектов по тикеру."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Общий интерфейс фиатной и криптовалюты."""

    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if not isinstance(code, str) or not (2 <= len(code) <= 5):
            raise ValueError("Код валюты должен содержать 2–5 символов")
        if code != code.upper() or not code.isalnum() or any(ch.isspace() for ch in code):
            raise ValueError("Код валюты должен быть в верхнем регистре без пробелов")
        self.name = name.strip()
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Вернуть человекочитаемое описание валюты."""


class FiatCurrency(Currency):
    """Фиатная валюта с указанием страны или зоны эмиссии."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        if not issuing_country.strip():
            raise ValueError("Страна/зона эмиссии не может быть пустой")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и последней известной капитализацией."""

    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float = 0.0,
    ) -> None:
        super().__init__(name, code)
        if not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if (
            isinstance(market_cap, bool)
            or not isinstance(market_cap, (int, float))
            or market_cap < 0
        ):
            raise ValueError("market_cap должен быть неотрицательным числом")
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


_CURRENCY_FACTORIES = {
    "USD": lambda: FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": lambda: FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": lambda: FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": lambda: FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": lambda: CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": lambda: CryptoCurrency("Ethereum", "ETH", "Ethash", 4.45e11),
    "SOL": lambda: CryptoCurrency("Solana", "SOL", "Proof of History", 7.0e10),
}


def get_currency(code: str) -> Currency:
    """Создать объект валюты по поддерживаемому коду."""
    normalized = code.strip().upper() if isinstance(code, str) else ""
    try:
        return _CURRENCY_FACTORIES[normalized]()
    except KeyError as exc:
        raise CurrencyNotFoundError(normalized or str(code)) from exc


def get_supported_codes() -> tuple[str, ...]:
    """Вернуть коды валют, поддерживаемых учебным реестром."""
    return tuple(_CURRENCY_FACTORIES)
