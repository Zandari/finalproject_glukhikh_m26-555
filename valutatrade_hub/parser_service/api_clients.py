"""Унифицированные клиенты CoinGecko и ExchangeRate-API."""

from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Общий интерфейс API-клиента; ключ словаря имеет формат FROM_TO."""

    source = "unknown"

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Вернуть словарь курсов в унифицированном формате."""


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko для криптовалют к USD."""

    source = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        mapping = self.config.CRYPTO_ID_MAP
        if not mapping:
            return {}
        try:
            response = requests.get(
                self.config.COINGECKO_URL,
                params={"ids": ",".join(mapping.values()), "vs_currencies": "usd"},
                timeout=self.config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            result = {}
            for code, coin_id in mapping.items():
                value = payload.get(coin_id, {}).get("usd")
                if isinstance(value, (int, float)) and value > 0:
                    result[f"{code}_USD"] = float(value)
            if not result:
                raise ApiRequestError("CoinGecko не вернул валидных курсов криптовалют")
            return result
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"CoinGecko: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise ApiRequestError(f"Некорректный ответ CoinGecko: {exc}") from exc


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API; нормализует курсы к формату EUR_USD."""

    source = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("не задан EXCHANGERATE_API_KEY в переменных окружения")
        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        )
        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            if payload.get("result") != "success":
                raise ApiRequestError(
                    f"ExchangeRate-API вернул ошибку: {payload.get('error-type', 'unknown')}"
                )
            rates = payload.get("conversion_rates", payload.get("rates", {}))
            result = {}
            for code in self.config.FIAT_CURRENCIES:
                value = rates.get(code)
                if isinstance(value, (int, float)) and value > 0:
                    # API даёт 1 USD = N EUR, а приложение хранит 1 EUR = N USD.
                    result[f"{code}_{self.config.BASE_CURRENCY}"] = 1.0 / float(value)
            if not result:
                raise ApiRequestError("ExchangeRate-API не вернул валидных фиатных курсов")
            return result
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"ExchangeRate-API: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise ApiRequestError(f"Некорректный ответ ExchangeRate-API: {exc}") from exc
